"""HTTP routes.

**Single job: the only module that knows about HTTP** — status codes, query
parameters, response models. It orchestrates repository + domain calls and owns
no business rules of its own.

All routes are product-scoped and deliberately live in one file: splitting seven
routes across a `routers/` package would be structure for its own sake at this
size (PLAN.md §7).
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Query

from app import repository
from app.domain import alternatives as alt
from app.domain import confidence as conf
from app.domain import delivery as dlv
from app.domain import pricing
from app.schemas import (
    AlternativeCard,
    AlternativesResponse,
    BrandOption,
    ConfidenceResponse,
    Destination,
    ProductCard,
    ProductDetail,
    RestockAlertRequest,
    RestockAlertResponse,
    Size,
    SizeAvailability,
    Style,
    UnavailableReason,
)

router = APIRouter(prefix="/api", tags=["confidence"])


def _now() -> datetime:
    """Local Pakistani time, deliberately naive.

    The seed stores discount expiries as naive local datetimes, and mixing naive
    and aware values raises at comparison time. Normalising here — once, at the
    boundary — keeps every downstream comparison safe. The domain layer still
    receives `now` as an argument rather than reading the clock itself, so tests
    stay deterministic.
    """
    return datetime.now(dlv.TIMEZONE).replace(tzinfo=None)


def _parse_expiry(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


# --------------------------------------------------------------------------
# Serialisation helpers
# --------------------------------------------------------------------------


def _card_fields(product: dict, now: datetime) -> dict:
    """The fields every listing-shaped response shares."""
    active = pricing.discount_is_active(
        product["discount_pct"], _parse_expiry(product["discount_ends_at"]), now
    )
    discounted = pricing.apply_discount(product["price_pkr"], product["discount_pct"], active)

    available = [v["size"] for v in product["variants"] if v["stock_qty"] > 0]

    return {
        "id": product["id"],
        "title": product["title"],
        "brand": product["brand"],
        "category": product["category"],
        "style": product["style"],
        "product_type": product["product_type"],
        "color": product["color"],
        "fabric": product["fabric"],
        "description_short": product["description_short"],
        "image_url": product["image_url"],
        "price_pkr": product["price_pkr"],
        "discounted_price_pkr": discounted,
        # An expired discount reports 0, so the UI cannot render a strikethrough
        # for a price that is no longer real.
        "discount_pct": product["discount_pct"] if active else 0,
        "available_sizes": available,
        "sold_out": not available,
    }


def _to_card(product: dict, now: datetime) -> ProductCard:
    return ProductCard(**_card_fields(product, now))


def _to_detail(product: dict, now: datetime) -> ProductDetail:
    sizes = [
        SizeAvailability(
            size=v["size"],
            status=repository.stock_status(v["stock_qty"]),
            units_left=(
                v["stock_qty"]
                if repository.stock_status(v["stock_qty"]) == "low_stock"
                else None
            ),
        )
        for v in product["variants"]
    ]
    return ProductDetail(
        **_card_fields(product, now),
        dispatch_city=product["dispatch_city"],
        dispatch_days=product["dispatch_days"],
        stitching_days=product["stitching_days"],
        ships_international=product["ships_international"],
        on_time_rate=product["on_time_rate"],
        sizes=sizes,
    )


def _require_product(product_id: str) -> dict:
    product = repository.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail=f"No product with id '{product_id}'")
    return product


def _resolve_destination(name: str | None) -> dict | None:
    """An unknown name is treated as *no* destination, not an error.

    A stale city in someone's `localStorage` should degrade to the cold-start
    experience, never break the page (edge case #16).
    """
    return repository.get_destination(name) if name else None


def _estimate_for(
    product: dict,
    size: str | None,
    destination: dict | None,
    now: datetime,
    with_stitching: bool = False,
):
    """Apply the refusal rules in priority order, then estimate.

    Order matters: a customer whose size is sold out needs to hear *that*, not
    that we don't ship to their country. The most actionable problem wins.
    """
    note = dlv.dispatch_note(
        product["dispatch_city"],
        product["dispatch_days"],
        product["stitching_days"] if with_stitching else 0,
    )

    if size is not None:
        variant = repository.variant_for(product, size)
        if variant is None or variant["stock_qty"] <= 0:
            return dlv.unavailable(UnavailableReason.OUT_OF_STOCK, note)
    elif not any(v["stock_qty"] > 0 for v in product["variants"]):
        return dlv.unavailable(UnavailableReason.OUT_OF_STOCK, note)

    if destination is None:
        return dlv.unavailable(UnavailableReason.NO_DESTINATION, note)
    if not destination["serviceable"]:
        return dlv.unavailable(UnavailableReason.NOT_SERVICEABLE, note)
    if destination["is_international"] and not product["ships_international"]:
        return dlv.unavailable(UnavailableReason.BRAND_NO_INTERNATIONAL, note)

    return dlv.estimate(
        dispatch_city=product["dispatch_city"],
        dispatch_days=product["dispatch_days"],
        stitching_days=product["stitching_days"],
        transit_days_min=destination["transit_days_min"],
        transit_days_max=destination["transit_days_max"],
        on_time_rate=product["on_time_rate"],
        now=now,
        with_stitching=with_stitching or product["product_type"] == "unstitched",
    )


# --------------------------------------------------------------------------
# Catalogue
# --------------------------------------------------------------------------


@router.get("/destinations", response_model=list[Destination])
def list_destinations() -> list[Destination]:
    """Populates the location picker, including destinations we cannot yet
    serve — we would rather say so at the gate than fail silently later."""
    return [Destination(**d) for d in repository.list_destinations()]


@router.get("/brands", response_model=list[BrandOption])
def list_brands() -> list[BrandOption]:
    return [BrandOption(**b) for b in repository.list_brands()]


@router.get("/products", response_model=list[ProductCard])
def list_products(
    style: Style | None = Query(None, description="eastern | western"),
    type: str | None = Query(None, alias="type", description="ready_to_wear | unstitched"),
    size: Size | None = Query(None, description="Only products in stock in this size."),
    brand: str | None = Query(None),
) -> list[ProductCard]:
    """Browse.

    Four independent filters. `size` is the discovery-to-confidence bridge: it
    answers "is it in my size?" before the click rather than after it.
    """
    now = _now()
    products = repository.list_products(
        style=style, product_type=type, size=size, brand=brand
    )
    return [_to_card(p, now) for p in products]


@router.get("/products/{product_id}", response_model=ProductDetail)
def get_product(product_id: str) -> ProductDetail:
    """Full detail with per-size stock *status*. 404 on unknown id."""
    return _to_detail(_require_product(product_id), _now())


# --------------------------------------------------------------------------
# Confidence
# --------------------------------------------------------------------------


@router.get("/products/{product_id}/confidence", response_model=ConfidenceResponse)
def get_confidence(
    product_id: str,
    size: Size | None = Query(None),
    destination: str | None = Query(None),
    arrive_by: date | None = Query(None),
    stitching: bool = Query(False, description="Unstitched only — adds stitching lead."),
) -> ConfidenceResponse:
    """Price + delivery + verdict, in one response.

    **Every parameter is optional and this must answer correctly when it knows
    nothing**, returning `unresolved` checks and ranged prices rather than an
    error. That is the cold-start state — the most-hit path on the whole API,
    and the one a naive implementation would reject with a 422.

    Merged from two endpoints during design: setting a destination resolves both
    the delivery date and the true total, so splitting them meant two round trips
    for a single user action (PLAN.md decision #5).
    """
    now = _now()
    product = _require_product(product_id)
    dest = _resolve_destination(destination)

    # Unwrap the enum at the boundary. Python 3.11 changed `__format__` for
    # str-mixin enums, so an f-string on `Size.S` renders "Size.S" — which would
    # leak straight into customer-facing copy. The domain deals in plain data.
    size_value = size.value if size else None

    # A deadline already in the past is a user error, not a server error: we
    # ignore it rather than 422-ing a page that is otherwise perfectly usable.
    if arrive_by is not None and arrive_by < now.date():
        arrive_by = None

    estimate = _estimate_for(product, size_value, dest, now, stitching)

    # A destination we cannot serve has no total. Computed before pricing so the
    # two panels can never contradict each other.
    undeliverable = estimate.reason in (
        UnavailableReason.NOT_SERVICEABLE,
        UnavailableReason.BRAND_NO_INTERNATIONAL,
    )

    price = pricing.breakdown(
        list_price_pkr=product["price_pkr"],
        discount_pct=product["discount_pct"],
        discount_ends_at=_parse_expiry(product["discount_ends_at"]),
        now=now,
        destination=dest,
        all_destinations=repository.list_destinations(),
        deliverable=not undeliverable,
    )

    in_time = dlv.arrives_in_time(estimate, arrive_by)

    variant = repository.variant_for(product, size_value) if size_value else None
    status = repository.stock_status(variant["stock_qty"]) if variant else None
    sold_out = not any(v["stock_qty"] > 0 for v in product["variants"])

    checks = [
        conf.size_check(
            size_value,
            status,
            variant["stock_qty"] if variant else None,
            product_sold_out=sold_out,
        ),
        conf.price_check(price),
        conf.delivery_check(estimate, arrive_by, in_time),
    ]
    verdict = conf.verdict_for(checks)

    return ConfidenceResponse(
        product_id=product_id,
        size=size,
        destination=dest["name"] if dest else None,
        arrive_by=arrive_by,
        price=price,
        delivery=estimate,
        checks=checks,
        verdict=verdict,
        cta=conf.cta_for(checks, verdict),
        failed_checks=conf.failed_check_ids(checks),
    )


@router.get("/products/{product_id}/alternatives", response_model=AlternativesResponse)
def get_alternatives(
    product_id: str,
    size: Size | None = Query(None),
    destination: str | None = Query(None),
    arrive_by: date | None = Query(None),
) -> AlternativesResponse:
    """Candidates that would do the same job and do not fail the same way.

    Returns an empty list with an `empty_reason` when nothing qualifies, rather
    than padding the rail with irrelevant products (edge case #11).
    """
    now = _now()
    base = _require_product(product_id)
    dest = _resolve_destination(destination)
    size_value = size.value if size else None

    # Recompute the base product's checks so the rail filters on the *current*
    # failure rather than trusting a client-supplied reason.
    base_estimate = _estimate_for(base, size_value, dest, now)
    base_in_time = dlv.arrives_in_time(base_estimate, arrive_by)
    variant = repository.variant_for(base, size_value) if size_value else None
    status = repository.stock_status(variant["stock_qty"]) if variant else None
    sold_out = not any(v["stock_qty"] > 0 for v in base["variants"])

    failed = conf.failed_check_ids(
        [
            conf.size_check(
                size_value,
                status,
                variant["stock_qty"] if variant else None,
                product_sold_out=sold_out,
            ),
            conf.delivery_check(base_estimate, arrive_by, base_in_time),
        ]
    )

    candidates = repository.list_products()
    if dest and arrive_by:
        # Only compute ETAs when a deadline actually needs judging — 35 estimate
        # calls is cheap, but pointless work is still pointless.
        for c in candidates:
            est = _estimate_for(c, size_value, dest, now)
            c["_arrives_to"] = est.arrives_to
        est_base = _estimate_for(base, size_value, dest, now)
        base["_arrives_to"] = est_base.arrives_to

    constraints = alt.Constraints(
        size=size_value,
        arrive_by=arrive_by,
        destination=dest["name"] if dest else None,
        is_international=bool(dest and dest["is_international"]),
    )

    ranked = alt.rank(base, candidates, constraints, failed)

    items = [
        AlternativeCard(**_card_fields(product, now), reasons=reasons, score=score)
        for product, score, reasons in ranked
    ]

    empty_reason = None
    if not items:
        if "delivery" in failed and arrive_by:
            empty_reason = (
                f"Nothing similar can reach {constraints.destination} "
                f"by {arrive_by.day} {arrive_by:%b}."
            )
        else:
            where = f" in {size_value}" if size_value else ""
            empty_reason = f"Nothing similar{where} right now."

    return AlternativesResponse(items=items, filtered_on=failed, empty_reason=empty_reason)


@router.post("/products/{product_id}/restock-alert", response_model=RestockAlertResponse)
def create_restock_alert(product_id: str, payload: RestockAlertRequest) -> RestockAlertResponse:
    """Capture demand for a sold-out size instead of losing the customer."""
    _require_product(product_id)
    repository.create_restock_alert(product_id, payload.size, payload.email, _now())
    return RestockAlertResponse(
        created=True,
        message=f"We'll let you know when size {payload.size.value} is back in stock.",
    )
