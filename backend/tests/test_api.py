"""Endpoint smoke tests.

Deliberately thin. The interesting logic is unit-tested in the domain suites
without a test client; these exist to prove the wiring holds and that the
cold-start contract is honoured at the HTTP boundary.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

TEAL = "noor-embroidered-lawn-3pc-teal"  # size M is seeded sold out
SOLD_OUT = "laalzari-luxury-pret-maroon"  # every size sold out


@pytest.fixture(scope="module")
def client():
    # The `with` block runs lifespan, which rebuilds the database from the seed.
    with TestClient(app) as c:
        yield c


def test_health_returns_ok(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_listing_returns_products(client):
    assert len(client.get("/api/products").json()) > 0


def test_listing_filtered_by_size_excludes_sold_out_products(client):
    """The discovery-to-confidence bridge."""
    ids = [p["id"] for p in client.get("/api/products", params={"size": "M"}).json()]
    assert TEAL not in ids  # M is sold out on this one
    assert SOLD_OUT not in ids


def test_listing_filters_combine(client):
    items = client.get("/api/products", params={"style": "western", "brand": "Zaria"}).json()
    assert all(p["style"] == "western" and p["brand"] == "Zaria" for p in items)


def test_brands_endpoint_returns_counts(client):
    brands = client.get("/api/brands").json()
    assert len(brands) == 8
    assert all(b["product_count"] > 0 for b in brands)


def test_destinations_include_unserviceable_ones(client):
    """We would rather tell someone at the gate than fail silently later."""
    dests = client.get("/api/destinations").json()
    assert any(d["serviceable"] is False for d in dests)


# --------------------------------------------------------------------------
# The cold-start contract
# --------------------------------------------------------------------------


def test_confidence_with_no_parameters_returns_200_and_unresolved_checks(client):
    """The most important API test in the file.

    A naive implementation makes size and destination required and returns 422
    here — which would break the state every first-time visitor is in.
    """
    r = client.get(f"/api/products/{TEAL}/confidence")
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"] == "incomplete"
    assert {c["status"] for c in body["checks"]} == {"unresolved"}


def test_cold_start_still_gives_an_exact_subtotal_and_a_ranged_total(client):
    price = client.get(f"/api/products/{TEAL}/confidence").json()["price"]
    assert price["subtotal_pkr"] > 0
    assert price["total_pkr"] is None
    assert price["total_range"]["min_pkr"] == price["subtotal_pkr"]


def test_cold_start_delivery_offers_the_dispatch_note(client):
    """Arrival is unknowable without a city; dispatch time is not."""
    delivery = client.get(f"/api/products/{TEAL}/confidence").json()["delivery"]
    assert delivery["available"] is False
    assert delivery["reason"] == "no_destination"
    assert "Ships from" in delivery["dispatch_note"]


def test_confidence_with_size_and_destination_resolves_every_check(client):
    body = client.get(
        f"/api/products/{TEAL}/confidence", params={"size": "S", "destination": "Lahore"}
    ).json()
    assert body["verdict"] == "ready"
    assert body["cta"] == "add_to_cart"
    assert body["price"]["total_pkr"] is not None


# --------------------------------------------------------------------------
# Failure paths
# --------------------------------------------------------------------------


def test_sold_out_size_blocks_and_offers_notify_me(client):
    body = client.get(
        f"/api/products/{TEAL}/confidence", params={"size": "M", "destination": "Lahore"}
    ).json()
    assert body["verdict"] == "blocked"
    assert body["cta"] == "notify_me"
    assert body["failed_checks"] == ["size"]


def test_sold_out_size_does_not_also_fail_the_delivery_check(client):
    """One problem, one red row. A delivery failure that is merely a consequence
    of the size failure would paint two, and would wrongly hard-filter the rail."""
    checks = client.get(
        f"/api/products/{TEAL}/confidence", params={"size": "M", "destination": "Lahore"}
    ).json()["checks"]
    delivery = next(c for c in checks if c["id"] == "delivery")
    assert delivery["status"] == "unresolved"


def test_unserviceable_destination_is_distinct_from_no_destination(client):
    body = client.get(
        f"/api/products/{TEAL}/confidence", params={"size": "S", "destination": "Gwadar"}
    ).json()
    assert body["delivery"]["reason"] == "not_serviceable"


def test_unknown_destination_degrades_to_cold_start_rather_than_erroring(client):
    """A stale city in someone's localStorage must not break the page."""
    r = client.get(
        f"/api/products/{TEAL}/confidence", params={"size": "S", "destination": "Atlantis"}
    )
    assert r.status_code == 200
    assert r.json()["delivery"]["reason"] == "no_destination"


def test_brand_that_does_not_ship_abroad_quotes_no_total(client):
    """The price card and the delivery panel must never contradict each other:
    if we cannot ship it there, there is no total for there."""
    body = client.get(
        "/api/products/meher-bridal-lehnga-crimson/confidence",
        params={"size": "S", "destination": "United Kingdom"},
    ).json()
    assert body["delivery"]["reason"] == "brand_no_international"
    assert body["price"]["deliverable"] is False
    assert body["price"]["total_pkr"] is None
    assert body["price"]["subtotal_pkr"] == 145000


def test_unserviceable_city_also_quotes_no_total(client):
    body = client.get(
        f"/api/products/{TEAL}/confidence", params={"size": "S", "destination": "Gwadar"}
    ).json()
    assert body["price"]["deliverable"] is False
    assert body["price"]["total_pkr"] is None


def test_deliverable_destination_still_quotes_a_total(client):
    body = client.get(
        f"/api/products/{TEAL}/confidence", params={"size": "S", "destination": "Lahore"}
    ).json()
    assert body["price"]["deliverable"] is True
    assert body["price"]["total_pkr"] is not None


def test_arrive_by_in_the_past_is_ignored_not_rejected(client):
    r = client.get(
        f"/api/products/{TEAL}/confidence",
        params={"size": "S", "destination": "Lahore", "arrive_by": "2020-01-01"},
    )
    assert r.status_code == 200
    assert r.json()["arrive_by"] is None


def test_confidence_for_unknown_product_returns_404(client):
    assert client.get("/api/products/nope/confidence").status_code == 404


def test_confidence_never_exposes_raw_stock_quantity(client):
    """Inventory data is not customer data (PLAN.md decision #8)."""
    detail = client.get(f"/api/products/{TEAL}").json()
    assert all("stock_qty" not in s for s in detail["sizes"])
    # units_left is only revealed when stock is genuinely low.
    for s in detail["sizes"]:
        assert s["units_left"] is None or s["status"] == "low_stock"


# --------------------------------------------------------------------------
# Alternatives
# --------------------------------------------------------------------------


def test_alternatives_are_in_stock_in_the_requested_size(client):
    items = client.get(
        f"/api/products/{TEAL}/alternatives", params={"size": "M", "destination": "Lahore"}
    ).json()["items"]
    assert items
    assert all("M" in i["available_sizes"] or i["product_type"] == "unstitched" for i in items)


def test_alternatives_carry_reasons(client):
    items = client.get(f"/api/products/{TEAL}/alternatives", params={"size": "M"}).json()["items"]
    assert all(i["reasons"] for i in items)


def test_alternatives_returns_empty_reason_when_nothing_qualifies(client):
    """Nothing in the catalogue can reach Canada by 10 Aug, so the rail must say
    so rather than pad itself with items that would also miss the date."""
    body = client.get(
        f"/api/products/{TEAL}/alternatives",
        params={"size": "S", "destination": "Canada", "arrive_by": "2026-08-10"},
    ).json()
    assert body["items"] == []
    assert "Canada" in body["empty_reason"]


# --------------------------------------------------------------------------
# Restock alerts
# --------------------------------------------------------------------------


def test_restock_alert_accepts_a_request_without_an_email(client):
    """Email is optional by design; the flow must work without collecting PII."""
    r = client.post(f"/api/products/{TEAL}/restock-alert", json={"size": "M"})
    assert r.status_code == 200
    assert r.json()["created"] is True


def test_restock_alert_rejects_an_invalid_email(client):
    r = client.post(
        f"/api/products/{TEAL}/restock-alert", json={"size": "M", "email": "not-an-email"}
    )
    assert r.status_code == 422
