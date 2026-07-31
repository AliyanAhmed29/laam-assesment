"""Alternatives ranking — what "similar" actually means.

Single job: given a product and (optionally) why it failed, rank candidates that
would do the same job and do not fail the same way.

Defining similarity
-------------------
The question a shopper is really asking is *"what else would do the job this
product was going to do?"* In South Asian fashion that job is mostly **occasion**
— a wedding formal does not substitute for a lawn 3-piece at any price. There is
no occasion tag in the catalogue, but three fields approximate it well: category,
price band, and fabric.

**Fabric is the domain-specific signal** and the reason this ranks better than a
generic recommender: fabric encodes both season and occasion in this market —
lawn is summer casual, chiffon and jamawar are formal, khaddar is winter. Two
same-priced pret suits in lawn are far closer substitutes than lawn and velvet.

**Colour is deliberately excluded.** Someone who liked a teal suit is often happy
with rose; colour variety is a feature of a good rail, not a defect.

The rule that makes this a confidence tool rather than a recommender
--------------------------------------------------------------------
**Hard-filter before scoring.** A candidate that fails the same check as the base
product is dropped outright, never merely down-ranked. Showing someone a "similar
item" that is also sold out in their size is worse than showing nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

# --------------------------------------------------------------------------
# Scoring weights (PLAN.md §10). Deterministic and pure, so the ranking is
# straightforwardly unit-testable.
# --------------------------------------------------------------------------

W_PASSES_FAILED_CHECK = 40.0
W_PRICE_PROXIMITY = 25.0
W_SAME_FABRIC = 15.0
W_SAME_TYPE = 10.0
W_ARRIVES_SOONER = 10.0
W_DIFFERENT_BRAND = 5.0

MAX_RESULTS = 6


@dataclass(frozen=True)
class Constraints:
    """What the customer actually needs. Every field may be None — the
    cold-start case still returns sensible generic alternatives."""

    size: str | None = None
    arrive_by: date | None = None
    destination: str | None = None
    is_international: bool = False


def price_proximity_score(base_price: int, candidate_price: int) -> float:
    """`25 * (1 - |delta| / base)`, clamped at 0.

    Clamping matters: without it a wildly expensive candidate earns a large
    negative score and distorts the ordering of everything else.
    """
    if base_price <= 0:
        return 0.0
    delta = abs(base_price - candidate_price) / base_price
    return max(0.0, W_PRICE_PROXIMITY * (1 - delta))


def _in_stock_in(candidate: dict, size: str | None) -> bool:
    """True when `size` is available, or when no size was requested.

    Unstitched pieces are `Free Size` and stitched to measurement, so they
    satisfy *any* requested size — hiding them from a size-filtered rail would
    suppress genuinely valid options (PLAN.md decision #15).
    """
    variants = candidate.get("variants", [])
    if size is None:
        return any(v["stock_qty"] > 0 for v in variants)
    if candidate.get("product_type") == "unstitched":
        return any(v["stock_qty"] > 0 for v in variants)
    return any(v["size"] == size and v["stock_qty"] > 0 for v in variants)


def passes_hard_filter(
    base: dict,
    candidate: dict,
    constraints: Constraints,
    failed_checks: list[str],
) -> bool:
    """Reject anything that would fail the customer the same way again."""
    if candidate["id"] == base["id"]:
        return False

    # Same job. A formal is not an alternative to a lawn suit at any price.
    if candidate["category"] != base["category"]:
        return False

    # An item they cannot wear is not an alternative, it is an ad.
    if not _in_stock_in(candidate, constraints.size):
        return False

    # Deliverable at all.
    if constraints.is_international and not candidate.get("ships_international", True):
        return False

    # Never repeat the specific failure the base product just produced.
    if "delivery" in failed_checks and constraints.arrive_by is not None:
        eta = candidate.get("_arrives_to")
        if eta is None or eta > constraints.arrive_by:
            return False

    return True


def score(base: dict, candidate: dict, constraints: Constraints, failed_checks: list[str]) -> float:
    """Sum of the weights above. Higher is better."""
    total = 0.0

    # Surviving the hard filter when a check failed *is* passing that check.
    if failed_checks:
        total += W_PASSES_FAILED_CHECK

    total += price_proximity_score(base["price_pkr"], candidate["price_pkr"])

    if candidate.get("fabric") == base.get("fabric"):
        total += W_SAME_FABRIC

    if candidate.get("product_type") == base.get("product_type"):
        total += W_SAME_TYPE

    base_eta, cand_eta = base.get("_arrives_to"), candidate.get("_arrives_to")
    if base_eta and cand_eta and cand_eta <= base_eta:
        total += W_ARRIVES_SOONER

    if candidate.get("brand") != base.get("brand"):
        total += W_DIFFERENT_BRAND

    return round(total, 2)


def reasons_for(candidate: dict, constraints: Constraints, base: dict) -> list[str]:
    """The labels rendered on the card.

    Concrete and checkable ("In stock in M", "Arrives Sat 8 Aug"), never vague
    ("Popular pick"). Each one must correspond to something the ranking actually
    verified — a card may not claim what was not checked.
    """
    reasons: list[str] = []

    if candidate.get("product_type") == "unstitched":
        reasons.append("Free Size — stitched to your measurements")
    elif constraints.size:
        reasons.append(f"In stock in {constraints.size}")

    if candidate.get("fabric") == base.get("fabric"):
        reasons.append(f"Same fabric — {candidate['fabric'].lower()}")

    if candidate["price_pkr"] < base["price_pkr"]:
        saving = base["price_pkr"] - candidate["price_pkr"]
        reasons.append(f"Rs {saving:,} less")

    if candidate.get("brand") != base.get("brand"):
        reasons.append(candidate["brand"])

    return reasons[:3]


def rank(
    base: dict,
    candidates: list[dict],
    constraints: Constraints,
    failed_checks: list[str] | None = None,
) -> list[tuple[dict, float, list[str]]]:
    """Filter, score, sort, and take the top `MAX_RESULTS`.

    Returns an empty list when nothing passes — the caller then says so plainly.
    Padding the rail with irrelevant products would undo the honesty the rest of
    the page is built on.

    Ties break on `id` so the ordering is stable; a rail that reshuffles between
    renders looks broken.
    """
    failed = failed_checks or []
    scored = [
        (c, score(base, c, constraints, failed), reasons_for(c, constraints, base))
        for c in candidates
        if passes_hard_filter(base, c, constraints, failed)
    ]
    scored.sort(key=lambda row: (-row[1], row[0]["id"]))
    return scored[:MAX_RESULTS]
