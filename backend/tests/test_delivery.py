"""Priority suite (PLAN.md §13).

Tested first because it has the most branching, the highest consequence if wrong,
and it is the pillar the whole design rests on — "can I trust the delivery
promise?" is meaningless if the estimator is `today + random(3, 7)`.

Note there are no fixtures, no test client and no database here. That is the
payoff of the layer rule: `domain/` imports neither FastAPI nor sqlite3, and
`now` is injected rather than read from the clock, so every case is deterministic.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from app.domain import delivery
from app.schemas import UnavailableReason

# 2026-08-14 is Independence Day; 2026-08-02 / 09 / 16 are Sundays.
MON_3_AUG = datetime(2026, 8, 3, 10, 0)
SAT_8_AUG = datetime(2026, 8, 8, 10, 0)


def estimate(now=MON_3_AUG, **overrides):
    """A ready-to-wear product from Lahore to a metro city, unless overridden."""
    params = dict(
        dispatch_city="Lahore",
        dispatch_days=2,
        stitching_days=0,
        transit_days_min=1,
        transit_days_max=2,
        on_time_rate=0.94,
        now=now,
    )
    params.update(overrides)
    return delivery.estimate(**params)


# --------------------------------------------------------------------------
# Working-day calendar
# --------------------------------------------------------------------------


def test_sunday_is_not_a_working_day():
    """Saturday is a working day for Pakistani couriers; Sunday is not."""
    assert delivery.is_working_day(date(2026, 8, 8)) is True  # Saturday
    assert delivery.is_working_day(date(2026, 8, 9)) is False  # Sunday


def test_public_holiday_is_not_a_working_day():
    """14 Aug 2026 (Independence Day) falls inside the demo's estimate window,
    so this is observable in the UI rather than a claim in a comment."""
    assert delivery.is_working_day(date(2026, 8, 14)) is False
    assert delivery.is_working_day(date(2026, 8, 13)) is True


def test_add_working_days_skips_non_working_days():
    # Fri 7 Aug + 1 working day skips Sun 9 Aug -> Mon 10 Aug via Sat 8 Aug.
    assert delivery.add_working_days(date(2026, 8, 7), 1) == date(2026, 8, 8)
    assert delivery.add_working_days(date(2026, 8, 7), 2) == date(2026, 8, 10)


def test_add_working_days_skips_the_holiday():
    # Thu 13 Aug + 1 must skip Fri 14 Aug (Independence Day) -> Sat 15 Aug.
    assert delivery.add_working_days(date(2026, 8, 13), 1) == date(2026, 8, 15)


def test_add_zero_working_days_rolls_forward_off_a_sunday():
    """`days == 0` must still land on a working day, otherwise a cutoff rollover
    onto a Sunday produces a dispatch date couriers do not operate on."""
    assert delivery.add_working_days(date(2026, 8, 9), 0) == date(2026, 8, 10)
    assert delivery.add_working_days(date(2026, 8, 10), 0) == date(2026, 8, 10)


def test_negative_working_days_is_rejected():
    with pytest.raises(ValueError):
        delivery.add_working_days(date(2026, 8, 10), -1)


def test_non_working_days_between_reports_what_was_skipped():
    skipped = delivery.non_working_days_between(date(2026, 8, 7), date(2026, 8, 17))
    assert date(2026, 8, 9) in skipped  # Sunday
    assert date(2026, 8, 14) in skipped  # Independence Day
    assert date(2026, 8, 10) not in skipped


# --------------------------------------------------------------------------
# Order cutoff
# --------------------------------------------------------------------------


def test_order_before_cutoff_starts_today():
    assert delivery.order_day(datetime(2026, 8, 3, 16, 59)) == date(2026, 8, 3)


def test_order_after_cutoff_starts_next_working_day():
    """16:59 and 17:01 on the same day must produce different promises."""
    assert delivery.order_day(datetime(2026, 8, 3, 17, 1)) == date(2026, 8, 4)


def test_order_after_cutoff_on_saturday_starts_monday():
    """Compound case: the cutoff rollover lands on Sunday, which is then skipped."""
    assert delivery.order_day(datetime(2026, 8, 8, 18, 0)) == date(2026, 8, 10)


def test_order_on_a_sunday_starts_monday_regardless_of_time():
    assert delivery.order_day(datetime(2026, 8, 9, 9, 0)) == date(2026, 8, 10)


# --------------------------------------------------------------------------
# The estimate itself
# --------------------------------------------------------------------------


def test_estimate_returns_a_range_not_a_single_date():
    est = estimate()
    assert est.available is True
    assert est.arrives_from is not None and est.arrives_to is not None
    assert est.arrives_from < est.arrives_to


def test_arrives_from_is_never_after_arrives_to():
    """Ordering invariant — cheap to assert, embarrassing to ship wrong."""
    for min_d, max_d in [(1, 2), (3, 3), (2, 9)]:
        est = estimate(transit_days_min=min_d, transit_days_max=max_d)
        assert est.arrives_from <= est.arrives_to


def test_unstitched_adds_stitching_lead_time():
    """The one piece of genuine LAAM domain knowledge in the build: unstitched
    fabric is cut to measurement, so it dispatches later than ready-to-wear."""
    plain = estimate()
    stitched = estimate(stitching_days=6, with_stitching=True)
    assert stitched.arrives_to > plain.arrives_to
    assert any("Stitched" in s.label for s in stitched.steps)


def test_stitching_not_added_when_not_requested():
    assert estimate(stitching_days=6).arrives_to == estimate().arrives_to


def test_international_zone_takes_longer_than_domestic_metro():
    domestic = estimate(transit_days_min=1, transit_days_max=2)
    intl = estimate(transit_days_min=8, transit_days_max=13)
    assert intl.arrives_to > domestic.arrives_to


def test_estimate_reports_the_holiday_it_skipped():
    """Independence Day must appear in `skipped_dates` when the window spans it,
    so the UI can explain why the date moved rather than looking arbitrary."""
    est = estimate(now=datetime(2026, 8, 12, 9, 0), transit_days_min=1, transit_days_max=3)
    assert date(2026, 8, 14) in est.skipped_dates


def test_steps_breakdown_ends_on_the_arrival_date():
    """The UI shows its working; the steps must reconcile to the dates."""
    est = estimate()
    assert est.steps[-1].ends_on == est.arrives_to
    assert est.steps[0].label.startswith("Brand dispatches")


def test_every_step_lands_on_a_working_day():
    est = estimate(stitching_days=5, with_stitching=True)
    for step in est.steps:
        assert delivery.is_working_day(step.ends_on)


# --------------------------------------------------------------------------
# Honest refusals — each reason drives a different recovery in the UI
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "reason",
    [
        UnavailableReason.OUT_OF_STOCK,
        UnavailableReason.NOT_SERVICEABLE,
        UnavailableReason.BRAND_NO_INTERNATIONAL,
        UnavailableReason.NO_DESTINATION,
    ],
)
def test_unavailable_carries_its_specific_reason_and_no_dates(reason):
    """Two different problems must not collapse into one generic error — each
    leads somewhere different in the UI."""
    est = delivery.unavailable(reason)
    assert est.available is False
    assert est.reason == reason
    assert est.arrives_from is None and est.arrives_to is None


def test_dispatch_note_is_available_without_a_destination():
    """Cold start: arrival is unknowable, but dispatch time is not — and saying
    something true beats saying nothing."""
    note = delivery.dispatch_note("Lahore", 2)
    assert "Lahore" in note and "2 working days" in note


def test_dispatch_note_singular_day_reads_correctly():
    assert "1 working day" in delivery.dispatch_note("Karachi", 1)


def test_dispatch_note_mentions_stitching_when_it_applies():
    note = delivery.dispatch_note("Faisalabad", 2, stitching_days=6)
    assert "measurements" in note and "8 working days" in note


# --------------------------------------------------------------------------
# Deadline judgement
# --------------------------------------------------------------------------


def test_arrives_in_time_judges_the_pessimistic_end_of_the_window():
    """Judged on `arrives_to`, not `arrives_from`.

    Telling a customer they will make their event based on the optimistic end of
    a range is exactly the confident-but-wrong claim this design exists to avoid.
    """
    est = estimate()  # 3 Aug + 2 dispatch -> 5 Aug, +1..2 transit -> 6..7 Aug
    assert delivery.arrives_in_time(est, est.arrives_to) is True
    assert delivery.arrives_in_time(est, est.arrives_from) is False


def test_arrives_in_time_is_none_without_a_deadline():
    assert delivery.arrives_in_time(estimate(), None) is None


def test_arrives_in_time_is_none_when_there_is_no_estimate():
    est = delivery.unavailable(UnavailableReason.OUT_OF_STOCK)
    assert delivery.arrives_in_time(est, date(2026, 12, 1)) is None
