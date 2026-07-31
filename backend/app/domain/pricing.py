"""Price resolution — "What will I actually pay?" answered literally.

Single job: turn (product, destination zone, "now") into a breakdown the customer
can read line by line.

Two decisions shape this module.

**GST is disclosed, never added.** Pakistani retail prices are tax-inclusive. If
we showed Rs 8,900 and then added 18% at the end, we would misrepresent how every
PK store prices *and* manufacture the exact surprise this design promises to
prevent. So GST is reported as a component of the total, not a line on top of it.

**Uncertainty lives in the shape of the value.** Before a destination is known
the delivery fee is genuinely unknown, so it is returned as a *range* rather than
a plausible-looking point estimate. `Rs 199` would be a lie; `Free - Rs 4,200`
is honest, because a range announces itself as a range.
"""

from __future__ import annotations

from datetime import datetime

from app.schemas import MoneyRange, PriceBreakdown, ValueSource

#: Standard Pakistani GST. Prices in this catalogue are inclusive of it.
GST_RATE_PCT = 18

#: Shown for international destinations. Disclosed, never computed — an invented
#: customs figure is exactly the dishonesty this build argues against.
DUTIES_NOTE = (
    "Import duties and local taxes are charged by your country's customs "
    "authority and are not included in this total."
)

DOMESTIC_ZONES = {"domestic_metro", "domestic_other"}


def discount_is_active(discount_pct: int, ends_at: datetime | None, now: datetime) -> bool:
    """An expired discount is simply not a discount.

    The UI then shows the original price with **no strikethrough** — a fake
    "was" price is a dark pattern, and this build's whole argument is honesty.
    """
    if discount_pct <= 0:
        return False
    if ends_at is None:
        return True
    return now < ends_at


def apply_discount(list_price_pkr: int, discount_pct: int, active: bool) -> int:
    """Subtotal after any live discount. Rounded to whole rupees — the catalogue
    deals in integers and half-rupees do not exist in practice."""
    if not active:
        return list_price_pkr
    return round(list_price_pkr * (100 - discount_pct) / 100)


def gst_component(subtotal_pkr: int) -> int:
    """The GST already *inside* a tax-inclusive amount.

    `subtotal * 18/118`, not `subtotal * 0.18` — the latter would be the tax on
    a tax-exclusive price and would overstate it by about 18%.
    """
    return round(subtotal_pkr * GST_RATE_PCT / (100 + GST_RATE_PCT))


def shipping_fee(subtotal_pkr: int, fee_pkr: int, free_threshold_pkr: int) -> int:
    """Zone fee, waived at or above the free-shipping threshold.

    `>=`, not `>`: a customer who lands exactly on the threshold has met it.
    """
    return 0 if subtotal_pkr >= free_threshold_pkr else fee_pkr


def fee_range(subtotal_pkr: int, destinations: list[dict]) -> MoneyRange | None:
    """Min/max shipping fee across a set of destinations, at this subtotal.

    Returns None for an empty set rather than a nonsensical 0-0 range.
    """
    fees = [
        shipping_fee(subtotal_pkr, d["shipping_fee_pkr"], d["free_shipping_threshold_pkr"])
        for d in destinations
        if d["serviceable"]
    ]
    if not fees:
        return None
    return MoneyRange(min_pkr=min(fees), max_pkr=max(fees))


def breakdown(
    *,
    list_price_pkr: int,
    discount_pct: int,
    discount_ends_at: datetime | None,
    now: datetime,
    destination: dict | None = None,
    all_destinations: list[dict] | None = None,
    deliverable: bool = True,
) -> PriceBreakdown:
    """Compute the payable breakdown.

    When `destination` is None (cold start) the subtotal is still **exact** —
    item price and discount are fully knowable — and shipping and total are
    returned as ranges computed from `all_destinations`, split domestic vs
    international because those are qualitatively different answers. Free
    shipping thresholds mean this often reads "Free within Pakistan ·
    Rs 1,900-4,200 international": two useful facts instead of one uselessly
    wide band.
    """
    active = discount_is_active(discount_pct, discount_ends_at, now)
    subtotal = apply_discount(list_price_pkr, discount_pct, active)
    discount_amount = list_price_pkr - subtotal

    common = {
        "list_price_pkr": list_price_pkr,
        "discount_pct": discount_pct if active else 0,
        "discount_active": active,
        "discount_amount_pkr": discount_amount,
        "subtotal_pkr": subtotal,
    }

    # ------------------------------------------------------- not deliverable
    # The customer named a destination we cannot ship this product to. Quoting
    # "Delivery: Free · Total Rs 145,000" would directly contradict the delivery
    # panel above it — there is no total for an address we cannot reach, and a
    # confident number here would be worse than an honest blank.
    if destination is not None and not deliverable:
        is_international = destination["zone"] not in DOMESTIC_ZONES
        return PriceBreakdown(
            **common,
            deliverable=False,
            gst_pkr=None if is_international else gst_component(subtotal),
            gst_rate_pct=GST_RATE_PCT,
            # No duties note here: it reads "not included in this total", and
            # there is no total. Warning someone about customs on a parcel that
            # will never be sent is noise.
            duties_note=None,
            source=ValueSource.UNRESOLVED,
        )

    # ---------------------------------------------------------------- resolved
    if destination is not None:
        is_international = destination["zone"] not in DOMESTIC_ZONES
        threshold = destination["free_shipping_threshold_pkr"]
        fee = shipping_fee(subtotal, destination["shipping_fee_pkr"], threshold)
        gap = max(0, threshold - subtotal) if fee > 0 else None

        return PriceBreakdown(
            **common,
            shipping_fee_pkr=fee,
            total_pkr=subtotal + fee,
            free_shipping_threshold_pkr=threshold,
            amount_to_free_shipping_pkr=gap,
            # Exports are zero-rated, so no GST line for international orders —
            # they get the disclosed duties note instead.
            gst_pkr=None if is_international else gst_component(subtotal),
            gst_rate_pct=GST_RATE_PCT,
            duties_note=DUTIES_NOTE if is_international else None,
            source=ValueSource.CONFIRMED,
        )

    # -------------------------------------------------------------- unresolved
    pool = all_destinations or []
    domestic = [d for d in pool if d["zone"] in DOMESTIC_ZONES]
    international = [d for d in pool if d["zone"] not in DOMESTIC_ZONES]

    domestic_range = fee_range(subtotal, domestic)
    international_range = fee_range(subtotal, international)

    overall = [r for r in (domestic_range, international_range) if r]
    total_range = (
        MoneyRange(
            min_pkr=subtotal + min(r.min_pkr for r in overall),
            max_pkr=subtotal + max(r.max_pkr for r in overall),
        )
        if overall
        else None
    )

    return PriceBreakdown(
        **common,
        domestic_shipping_range=domestic_range,
        international_shipping_range=international_range,
        total_range=total_range,
        # GST is knowable now — it is a component of the subtotal, which does
        # not depend on where the parcel goes. Only its *applicability* does,
        # and until we know the country we quote the domestic case.
        gst_pkr=gst_component(subtotal),
        gst_rate_pct=GST_RATE_PCT,
        source=ValueSource.ESTIMATED,
    )
