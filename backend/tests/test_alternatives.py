"""Ranking tests.

The single most important assertion in this file is the hard filter: an
alternative that fails the same way as the base product must never appear.
Showing someone a "similar item" that is also sold out in their size is worse
than showing nothing at all.
"""

from __future__ import annotations

from datetime import date

from app.domain import alternatives as alt


def product(pid, **overrides):
    p = {
        "id": pid,
        "brand": "Noor Studio",
        "category": "pret",
        "product_type": "ready_to_wear",
        "fabric": "Lawn",
        "price_pkr": 8000,
        "ships_international": True,
        "variants": [{"size": "S", "stock_qty": 5}, {"size": "M", "stock_qty": 5}],
    }
    p.update(overrides)
    return p


BASE = product("base")


# --------------------------------------------------------------------------
# The hard filter
# --------------------------------------------------------------------------


def test_hard_filter_never_leaks_a_same_failure_candidate():
    """The rule the whole module exists to enforce."""
    sold_out_in_m = product("other", variants=[{"size": "M", "stock_qty": 0}])
    ranked = alt.rank(BASE, [sold_out_in_m], alt.Constraints(size="M"), ["size"])
    assert ranked == []


def test_different_category_is_never_an_alternative():
    """A wedding formal does not substitute for a lawn 3-piece at any price."""
    formal = product("formal", category="formals")
    assert alt.rank(BASE, [formal], alt.Constraints(), []) == []


def test_base_product_never_appears_in_its_own_alternatives():
    assert alt.rank(BASE, [BASE], alt.Constraints(), []) == []


def test_candidate_that_cannot_arrive_in_time_is_dropped():
    late = product("late", _arrives_to=date(2026, 8, 20))
    ontime = product("ontime", _arrives_to=date(2026, 8, 5))
    constraints = alt.Constraints(size="M", arrive_by=date(2026, 8, 10))
    ids = [c["id"] for c, _, _ in alt.rank(BASE, [late, ontime], constraints, ["delivery"])]
    assert ids == ["ontime"]


def test_brand_without_international_shipping_dropped_for_export():
    domestic_only = product("domestic", ships_international=False)
    constraints = alt.Constraints(size="M", is_international=True)
    assert alt.rank(BASE, [domestic_only], constraints, []) == []


def test_unstitched_satisfies_any_requested_size():
    """Free Size is stitched to measurement, so it always fits. Hiding it from a
    size-filtered rail would suppress genuinely valid options (decision #15)."""
    unstitched = product(
        "unstitched",
        product_type="unstitched",
        variants=[{"size": "Free Size", "stock_qty": 10}],
    )
    ranked = alt.rank(BASE, [unstitched], alt.Constraints(size="XL"), ["size"])
    assert [c["id"] for c, _, _ in ranked] == ["unstitched"]


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------


def test_price_proximity_score_is_clamped_at_zero():
    """Without clamping, a wildly expensive candidate earns a large negative
    score and distorts the ordering of everything else."""
    assert alt.price_proximity_score(8000, 100000) == 0.0


def test_price_proximity_is_maximal_at_an_identical_price():
    assert alt.price_proximity_score(8000, 8000) == alt.W_PRICE_PROXIMITY


def test_closer_priced_candidate_outranks_a_distant_one():
    near = product("near", price_pkr=8200)
    far = product("far", price_pkr=14000)
    ids = [c["id"] for c, _, _ in alt.rank(BASE, [far, near], alt.Constraints(), [])]
    assert ids == ["near", "far"]


def test_same_fabric_outranks_a_different_fabric_at_equal_price():
    """Fabric encodes season and occasion in this market — the domain-specific
    signal that makes this better than a generic recommender."""
    same = product("same-fabric", fabric="Lawn")
    other = product("other-fabric", fabric="Velvet")
    ids = [c["id"] for c, _, _ in alt.rank(BASE, [other, same], alt.Constraints(), [])]
    assert ids == ["same-fabric", "other-fabric"]


def test_results_are_capped_at_max_results():
    many = [product(f"p{i}", price_pkr=8000 + i) for i in range(20)]
    assert len(alt.rank(BASE, many, alt.Constraints(), [])) == alt.MAX_RESULTS


def test_ranking_is_deterministic_and_stable():
    """Same inputs, same order — otherwise the rail reshuffles between renders
    and looks broken."""
    tied = [product("b"), product("a"), product("c")]
    first = [c["id"] for c, _, _ in alt.rank(BASE, tied, alt.Constraints(), [])]
    second = [c["id"] for c, _, _ in alt.rank(BASE, list(reversed(tied)), alt.Constraints(), [])]
    assert first == second == ["a", "b", "c"]


# --------------------------------------------------------------------------
# Output contract
# --------------------------------------------------------------------------


def test_empty_when_nothing_passes_rather_than_padding():
    """Edge case #11. Padding the rail would undo the honesty the rest of the
    page is built on."""
    assert alt.rank(BASE, [], alt.Constraints(), []) == []


def test_every_result_carries_at_least_one_reason():
    """A card with no stated reason is a recommendation, not an answer."""
    ranked = alt.rank(BASE, [product("other", brand="Meher")], alt.Constraints(size="M"), [])
    assert all(reasons for _, _, reasons in ranked)


def test_reasons_state_the_size_that_was_actually_checked():
    ranked = alt.rank(BASE, [product("other")], alt.Constraints(size="M"), [])
    assert "In stock in M" in ranked[0][2]


def test_reasons_mention_a_genuine_saving_only():
    cheaper = product("cheap", price_pkr=6000)
    reasons = alt.rank(BASE, [cheaper], alt.Constraints(), [])[0][2]
    assert any("2,000 less" in r for r in reasons)
