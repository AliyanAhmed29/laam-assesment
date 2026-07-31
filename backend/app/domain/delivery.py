"""Delivery estimation — the centrepiece of this build.

Single job: turn (product, size availability, destination zone, "now") into an
honest arrival window, or an honest refusal.

Why this module carries the most weight
---------------------------------------
"Can I trust the delivery promise?" is one of the five questions in the brief. If
this returned ``today + random(3, 7)`` the whole pillar would be theatre. So the
calculation is real: an order cutoff, brand handling time, stitching lead for
unstitched pieces, zone transit, and a working-day calendar that skips Sundays
and public holidays.

Two rules it never breaks:

1. **A range, never a single date.** A precise wrong date destroys more trust
   than an honest window.
2. **Refuse rather than fabricate.** If the size is out of stock, the destination
   is unserviceable, or the brand does not ship internationally, return
   ``available=False`` with a distinct reason — each drives a different recovery.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.schemas import DeliveryEstimate, DeliveryStep, UnavailableReason, ValueSource

# --------------------------------------------------------------------------
# Domain constants — deliberately here, beside the logic that reads them,
# rather than in a config module (PLAN.md §7).
# --------------------------------------------------------------------------

TIMEZONE = ZoneInfo("Asia/Karachi")

#: Orders placed after this local time start their clock the next working day.
ORDER_CUTOFF = time(17, 0)

#: Pakistani couriers generally run Saturdays; Sunday is the non-working day.
#: `date.weekday()` -> Monday is 0, Sunday is 6.
NON_WORKING_WEEKDAYS = {6}

#: Public holidays couriers do not operate on.
#: 14 August 2026 (Independence Day) falls inside the current estimate window,
#: so this table visibly shifts dates in the demo rather than being an
#: unobservable claim.
PUBLIC_HOLIDAYS: dict[date, str] = {
    date(2026, 8, 14): "Independence Day",
    date(2026, 9, 6): "Defence Day",
}

#: Guard against a runaway loop if the holiday table were ever misconfigured.
_MAX_SCAN_DAYS = 400


def is_working_day(day: date) -> bool:
    """True if couriers operate on `day`."""
    return day.weekday() not in NON_WORKING_WEEKDAYS and day not in PUBLIC_HOLIDAYS


def next_working_day(day: date) -> date:
    """The first working day on or after `day`."""
    for _ in range(_MAX_SCAN_DAYS):
        if is_working_day(day):
            return day
        day += timedelta(days=1)
    raise ValueError("no working day found — holiday table is misconfigured")


def add_working_days(start: date, days: int) -> date:
    """Advance `start` by `days` working days, skipping Sundays and holidays.

    `days == 0` returns the next working day on or after `start`, so a cutoff
    rollover that lands on a Sunday still produces a sane dispatch date.
    """
    if days < 0:
        raise ValueError("days must not be negative")

    current = next_working_day(start)
    remaining = days
    while remaining > 0:
        current = next_working_day(current + timedelta(days=1))
        remaining -= 1
    return current


def non_working_days_between(start: date, end: date) -> list[date]:
    """Non-working dates in `(start, end]`.

    Surfaced to the client so the UI can explain *why* a date moved — "skips Sun
    9 Aug and Independence Day" is the difference between a date that looks
    arbitrary and one that looks reasoned.
    """
    skipped: list[date] = []
    day = start + timedelta(days=1)
    while day <= end:
        if not is_working_day(day):
            skipped.append(day)
        day += timedelta(days=1)
    return skipped


def order_day(now: datetime) -> date:
    """The day the clock actually starts.

    Before the 17:00 cutoff on a working day that is today; after it — or on a
    non-working day — it is the next working day.
    """
    today = now.date()
    if is_working_day(today) and now.time() < ORDER_CUTOFF:
        return today
    return next_working_day(today + timedelta(days=1))


def dispatch_note(city: str, dispatch_days: int, stitching_days: int = 0) -> str:
    """What is knowable *without* a destination.

    Deliberately shown at cold start instead of an arrival range: "3-20 days"
    spanning Lahore-to-Canada is noise, but "ships from Lahore in 2 working
    days" is genuinely useful and completely certain (PLAN.md decision #13).
    """
    total = dispatch_days + stitching_days
    unit = "working day" if total == 1 else "working days"
    if stitching_days:
        return f"Stitched to your measurements and shipped from {city} in {total} {unit}"
    return f"Ships from {city} in {total} {unit}"


def unavailable(reason: UnavailableReason, note: str | None = None) -> DeliveryEstimate:
    """An honest blank. Always preferred over a fabricated date."""
    return DeliveryEstimate(
        available=False,
        reason=reason,
        dispatch_note=note,
        source=ValueSource.UNRESOLVED,
    )


def estimate(
    *,
    dispatch_city: str,
    dispatch_days: int,
    stitching_days: int,
    transit_days_min: int,
    transit_days_max: int,
    on_time_rate: float,
    now: datetime,
    with_stitching: bool = False,
) -> DeliveryEstimate:
    """Compute the arrival window.

        1. order_day      = today, or next working day if past the cutoff
        2. dispatch_ready = order_day + dispatch_days            (working days)
        3. if with_stitching: dispatch_ready += stitching_days   (working days)
        4. arrives_from   = dispatch_ready + transit_days_min    (working days)
           arrives_to     = dispatch_ready + transit_days_max    (working days)

    `now` is injected rather than read from the clock so the tests are
    deterministic — the single most important testability decision in the
    backend.

    Returns the window plus a step-by-step breakdown, so the front end can show
    its working instead of asserting a date.
    """
    started = order_day(now)
    steps: list[DeliveryStep] = []

    dispatch_ready = add_working_days(started, dispatch_days)
    steps.append(
        DeliveryStep(
            label=f"Brand dispatches from {dispatch_city}",
            days=dispatch_days,
            ends_on=dispatch_ready,
        )
    )

    if with_stitching and stitching_days:
        dispatch_ready = add_working_days(dispatch_ready, stitching_days)
        steps.append(
            DeliveryStep(
                label="Stitched to your measurements",
                days=stitching_days,
                ends_on=dispatch_ready,
            )
        )

    arrives_from = add_working_days(dispatch_ready, transit_days_min)
    arrives_to = add_working_days(dispatch_ready, transit_days_max)

    steps.append(
        DeliveryStep(
            label="In transit",
            days=transit_days_max,
            ends_on=arrives_to,
        )
    )

    # Invariant: a min window can never land after a max window. Cheap to
    # assert, embarrassing to ship wrong.
    if arrives_from > arrives_to:
        arrives_from, arrives_to = arrives_to, arrives_from

    return DeliveryEstimate(
        available=True,
        arrives_from=arrives_from,
        arrives_to=arrives_to,
        steps=steps,
        skipped_dates=non_working_days_between(started, arrives_to),
        dispatch_note=dispatch_note(
            dispatch_city, dispatch_days, stitching_days if with_stitching else 0
        ),
        on_time_rate=on_time_rate,
        source=ValueSource.CONFIRMED,
    )


def arrives_in_time(estimate_: DeliveryEstimate, arrive_by: date | None) -> bool | None:
    """Whether the *whole* window lands on or before the deadline.

    Judged on `arrives_to`, not `arrives_from`: promising a customer they will
    make their event based on the optimistic end of a range is exactly the kind
    of confident-but-wrong claim this design exists to avoid.

    Returns None when there is no deadline or no estimate to judge.
    """
    if arrive_by is None or not estimate_.available or estimate_.arrives_to is None:
        return None
    return estimate_.arrives_to <= arrive_by
