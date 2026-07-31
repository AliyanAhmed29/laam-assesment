"""Verdict assembly — turns three independent facts into one decision.

Single job: fold the size / price / delivery checks into a `verdict` and the CTA
the page should show.

This module is what earns the confidence card its place on screen. It justifies
itself only by producing a single verdict, owning the unresolved-state prompts,
and driving the CTA — if it ever degrades into restating three facts already
visible elsewhere, delete it (PLAN.md §10 kill condition).

The precedence rule is the whole module: **fail beats unresolved beats ok.** A
page with one failed check and one unknown is blocked, not incomplete — the
failure is the more actionable fact and must not be buried.
"""

from __future__ import annotations

from datetime import date

from app.schemas import (
    Check,
    CheckStatus,
    Cta,
    DeliveryEstimate,
    PriceBreakdown,
    StockStatus,
    UnavailableReason,
    Verdict,
)

#: At or below this, the customer sees "Only N left" instead of a plain tick.
#: Honest scarcity: no countdown timers, no "12 people are viewing this".
LOW_STOCK_THRESHOLD = 3

#: Human-readable copy for each refusal. Kept beside the logic so the reason
#: codes and the sentences a customer reads cannot drift apart.
DELIVERY_FAILURE_COPY = {
    UnavailableReason.OUT_OF_STOCK: "Not available in this size",
    UnavailableReason.NOT_SERVICEABLE: "We don't deliver here yet",
    UnavailableReason.BRAND_NO_INTERNATIONAL: "This brand ships within Pakistan only",
}


def _day_month(value: date) -> str:
    """'8 Aug'.

    Built by hand rather than with `%-d`/`%#d`: those directives are
    platform-specific (POSIX vs Windows) and would make the backend crash on
    one of them. `value.day` is portable.
    """
    return f"{value.day} {value:%b}"


def size_check(
    size: str | None,
    status: StockStatus | None,
    units_left: int | None = None,
    product_sold_out: bool = False,
) -> Check:
    """`unresolved` when no size is picked — the cold-start default, and a
    legitimate answer rather than an error.

    Size is never guessed on the customer's behalf: a wrong guess corrupts the
    single number they came to check (PLAN.md decision #7).
    """
    # Edge #3: nothing to select. Prompting for a size the customer cannot
    # possibly choose would be a dead end dressed up as an unresolved state.
    if product_sold_out:
        return Check(
            id="size",
            status=CheckStatus.FAIL,
            label="Sold out in every size",
            detail="See similar pieces that are in stock",
        )

    if size is None:
        return Check(
            id="size",
            status=CheckStatus.UNRESOLVED,
            label="Select a size",
            detail="Choose your size to check availability",
        )

    if status == StockStatus.OUT_OF_STOCK:
        return Check(
            id="size",
            status=CheckStatus.FAIL,
            label=f"Size {size} — sold out",
            detail="See what else is available in your size",
        )

    if status == StockStatus.LOW_STOCK:
        left = f"Only {units_left} left" if units_left else "Low stock"
        return Check(id="size", status=CheckStatus.OK, label=f"Size {size} — {left.lower()}")

    return Check(id="size", status=CheckStatus.OK, label=f"Size {size} — in stock")


def price_check(price: PriceBreakdown) -> Check:
    """`unresolved` until a destination is known.

    Note this is *unresolved*, not *failed*: we still show a real total range,
    so the customer is not stuck — they simply have not told us enough for an
    exact figure yet.
    """
    # We know the destination; we simply cannot serve it. The delivery row
    # already explains why, so this stays unresolved rather than painting a
    # second red row for the same underlying problem.
    if not price.deliverable:
        return Check(
            id="price",
            status=CheckStatus.UNRESOLVED,
            label=f"Item price Rs {price.subtotal_pkr:,}",
            detail="No delivery total — we can't ship this here",
        )

    if price.total_pkr is None:
        return Check(
            id="price",
            status=CheckStatus.UNRESOLVED,
            label="Total depends on delivery",
            detail="Select your city for the exact amount",
        )

    return Check(
        id="price",
        status=CheckStatus.OK,
        label=f"Total Rs {price.total_pkr:,}",
        detail="Delivery included" if price.shipping_fee_pkr == 0 else None,
    )


def delivery_check(
    delivery: DeliveryEstimate,
    arrive_by: date | None,
    in_time: bool | None = None,
) -> Check:
    """Four outcomes worth distinguishing.

    A missing estimate is only *unresolved* when the cause is us not knowing the
    destination yet. Every other cause is a genuine failure with its own
    recovery, so they must not collapse into one generic error.
    """
    if not delivery.available:
        if delivery.reason == UnavailableReason.NO_DESTINATION:
            return Check(
                id="delivery",
                status=CheckStatus.UNRESOLVED,
                label="Select your city for delivery dates",
                detail=delivery.dispatch_note,
            )

        # An out-of-stock size already produces its own failed row. Reporting it
        # again here would paint two red rows for one problem, and would put
        # "delivery" into failed_checks — which then hard-filters the
        # alternatives rail on a constraint that never actually failed.
        # One problem, one red row.
        if delivery.reason == UnavailableReason.OUT_OF_STOCK:
            return Check(
                id="delivery",
                status=CheckStatus.UNRESOLVED,
                label="Delivery shown once a size is available",
                detail=delivery.dispatch_note,
            )

        return Check(
            id="delivery",
            status=CheckStatus.FAIL,
            label=DELIVERY_FAILURE_COPY.get(delivery.reason, "Delivery unavailable"),
            detail=delivery.dispatch_note,
        )

    if delivery.arrives_from == delivery.arrives_to:
        window = f"Arrives {_day_month(delivery.arrives_to)}"
    else:
        window = (
            f"Arrives {_day_month(delivery.arrives_from)} – "
            f"{_day_month(delivery.arrives_to)}"
        )

    if in_time is False:
        return Check(
            id="delivery",
            status=CheckStatus.FAIL,
            label=f"{window} — after {_day_month(arrive_by)}",
            detail="See what can arrive in time",
        )

    return Check(id="delivery", status=CheckStatus.OK, label=window)


def verdict_for(checks: list[Check]) -> Verdict:
    """`blocked` if anything failed, else `incomplete` if anything is
    unresolved, else `ready`."""
    statuses = {c.status for c in checks}
    if CheckStatus.FAIL in statuses:
        return Verdict.BLOCKED
    if CheckStatus.UNRESOLVED in statuses:
        return Verdict.INCOMPLETE
    return Verdict.READY


def cta_for(checks: list[Check], verdict: Verdict) -> Cta:
    """Which action the page offers.

    Derived from the checks rather than chosen by the UI, so the button can
    never disagree with the rows printed directly above it.
    """
    by_id = {c.id: c for c in checks}

    if by_id.get("size") and by_id["size"].status == CheckStatus.FAIL:
        return Cta.NOTIFY_ME
    if by_id.get("delivery") and by_id["delivery"].status == CheckStatus.FAIL:
        return Cta.SEE_ALTERNATIVES
    if by_id.get("size") and by_id["size"].status == CheckStatus.UNRESOLVED:
        return Cta.SELECT_SIZE
    if verdict == Verdict.BLOCKED:
        return Cta.SEE_ALTERNATIVES
    return Cta.ADD_TO_CART


def failed_check_ids(checks: list[Check]) -> list[str]:
    """Drives the hard filter on the alternatives rail."""
    return [c.id for c in checks if c.status == CheckStatus.FAIL]
