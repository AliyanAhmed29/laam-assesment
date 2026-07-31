"""Second priority suite.

Money is the other number a customer will hold you to. The boundary cases here
(exactly at the free-shipping threshold, a discount expiring mid-session, tax on
a tax-inclusive price) are where naive implementations quietly disagree with
checkout.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.domain import pricing
from app.schemas import ValueSource

NOW = datetime(2026, 8, 1, 12, 0)

LAHORE = {
    "name": "Lahore",
    "zone": "domestic_metro",
    "shipping_fee_pkr": 199,
    "free_shipping_threshold_pkr": 5000,
    "serviceable": True,
}
USA = {
    "name": "United States",
    "zone": "intl_west",
    "shipping_fee_pkr": 3900,
    "free_shipping_threshold_pkr": 35000,
    "serviceable": True,
}
GWADAR = {
    "name": "Gwadar",
    "zone": "domestic_other",
    "shipping_fee_pkr": 0,
    "free_shipping_threshold_pkr": 5000,
    "serviceable": False,
}
ALL_DESTINATIONS = [LAHORE, USA, GWADAR]


def breakdown(**overrides):
    params = dict(
        list_price_pkr=8900,
        discount_pct=0,
        discount_ends_at=None,
        now=NOW,
        destination=LAHORE,
        all_destinations=ALL_DESTINATIONS,
    )
    params.update(overrides)
    return pricing.breakdown(**params)


# --------------------------------------------------------------------------
# Discounts
# --------------------------------------------------------------------------


def test_discount_applied_when_active():
    b = breakdown(discount_pct=15, discount_ends_at=datetime(2026, 8, 20))
    assert b.discount_active is True
    assert b.subtotal_pkr == 7565
    assert b.discount_amount_pkr == 1335


def test_expired_discount_falls_back_to_list_price():
    """And `discount_pct` must report 0, so the UI cannot render a strikethrough
    for a price that is no longer real — a fake 'was' price is the exact
    dishonesty this build argues against."""
    b = breakdown(discount_pct=25, discount_ends_at=datetime(2026, 7, 10))
    assert b.discount_active is False
    assert b.subtotal_pkr == 8900
    assert b.discount_amount_pkr == 0


def test_discount_with_no_expiry_never_expires():
    assert breakdown(discount_pct=10, discount_ends_at=None).discount_active is True


def test_zero_percent_is_not_an_active_discount():
    assert breakdown(discount_pct=0, discount_ends_at=datetime(2099, 1, 1)).discount_active is False


# --------------------------------------------------------------------------
# Free-shipping threshold
# --------------------------------------------------------------------------


def test_subtotal_exactly_at_free_shipping_threshold_ships_free():
    """Boundary: `>=`, not `>`. A customer who lands exactly on the threshold
    has met it, and off-by-one here is customer-visible."""
    assert pricing.shipping_fee(5000, 199, 5000) == 0


def test_subtotal_one_rupee_under_threshold_pays_shipping():
    assert pricing.shipping_fee(4999, 199, 5000) == 199


def test_amount_to_free_shipping_is_reported_when_short():
    b = breakdown(list_price_pkr=4800)
    assert b.shipping_fee_pkr == 199
    assert b.amount_to_free_shipping_pkr == 200


def test_amount_to_free_shipping_is_none_once_qualified():
    assert breakdown(list_price_pkr=8900).amount_to_free_shipping_pkr is None


# --------------------------------------------------------------------------
# GST — disclosed, never added
# --------------------------------------------------------------------------


def test_gst_is_extracted_from_a_tax_inclusive_price():
    """`subtotal * 18/118`, not `subtotal * 0.18`.

    The latter is the tax on a tax-exclusive price and overstates it by ~18%.
    Pakistani retail prices are quoted inclusive of GST.
    """
    assert pricing.gst_component(11800) == 1800


def test_gst_never_increases_the_total():
    """The whole point: tax is a component of the total, not a line on top of
    it. Adding it would manufacture the surprise we promise to prevent."""
    b = breakdown(list_price_pkr=8900)
    assert b.total_pkr == b.subtotal_pkr + b.shipping_fee_pkr
    assert b.gst_pkr < b.subtotal_pkr


def test_international_destination_is_zero_rated_and_shows_duties_note():
    b = breakdown(destination=USA)
    assert b.gst_pkr is None
    assert b.duties_note is not None


def test_domestic_destination_has_no_duties_note():
    assert breakdown(destination=LAHORE).duties_note is None


# --------------------------------------------------------------------------
# Unresolved — the cold-start path
# --------------------------------------------------------------------------


def test_subtotal_is_exact_even_without_a_destination():
    """Item price and discount are fully knowable now, so they anchor the card
    while the delivery-dependent rows stay ranged."""
    b = breakdown(destination=None, discount_pct=15, discount_ends_at=datetime(2026, 8, 20))
    assert b.subtotal_pkr == 7565
    assert b.source == ValueSource.ESTIMATED


def test_total_is_none_and_ranged_until_destination_is_known():
    b = breakdown(destination=None)
    assert b.total_pkr is None
    assert b.shipping_fee_pkr is None
    assert b.total_range is not None
    assert b.total_range.min_pkr == b.subtotal_pkr


def test_unresolved_splits_domestic_from_international():
    """One combined range spanning Lahore to Canada would be uselessly wide;
    two ranges are two useful facts."""
    b = breakdown(list_price_pkr=8900, destination=None)
    assert b.domestic_shipping_range.max_pkr == 0  # over the Rs 5,000 threshold
    assert b.international_shipping_range.min_pkr == 3900


def test_unresolved_range_excludes_unserviceable_destinations():
    """Gwadar is not serviceable, so quoting its Rs 0 fee would understate the
    real range."""
    b = breakdown(list_price_pkr=1000, destination=None)
    assert b.domestic_shipping_range.min_pkr == 199


def test_fee_range_is_none_for_an_empty_destination_set():
    assert pricing.fee_range(5000, []) is None


# --------------------------------------------------------------------------
# Undeliverable destinations
# --------------------------------------------------------------------------


def test_undeliverable_destination_has_no_total_at_all():
    """There is no total for an address we cannot reach.

    Quoting "Delivery: Free · Total Rs 145,000" beside a panel saying we don't
    ship there would have the two halves of the card contradict each other.
    """
    b = breakdown(destination=USA, deliverable=False)
    assert b.deliverable is False
    assert b.total_pkr is None
    assert b.shipping_fee_pkr is None
    assert b.total_range is None


def test_undeliverable_still_reports_the_exact_item_price():
    """The price of the garment is still a true fact worth showing."""
    b = breakdown(list_price_pkr=145000, destination=USA, deliverable=False)
    assert b.subtotal_pkr == 145000


def test_deliverable_is_true_by_default():
    assert breakdown().deliverable is True


def test_cheap_item_shows_a_real_domestic_fee_range():
    b = breakdown(list_price_pkr=1200, destination=None)
    assert b.total_range.min_pkr == 1200 + 199
    assert b.total_range.max_pkr == 1200 + 3900
