"""Data access.

**Single job: the only module in the codebase that writes SQL.** Everything above
it deals in plain dicts and Pydantic models.

That boundary is what makes "swap SQLite for PostgreSQL" an honest one-class
change rather than a rewrite — worth stating in README §8, since LAAM's own
backend role is Postgres-based.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from app.db import connect
from app.domain.confidence import LOW_STOCK_THRESHOLD
from app.schemas import StockStatus, Style

#: Everything that is not western is eastern; unstitched is always eastern.
#: Derived rather than stored, so the two browse axes stay independent.
EASTERN_CATEGORIES = ("pret", "formals", "unstitched")
WESTERN_CATEGORIES = ("west",)

DOMESTIC_ZONES = ("domestic_metro", "domestic_other")


def _rows_to_products(rows: list[sqlite3.Row], variant_rows: list[sqlite3.Row]) -> list[dict]:
    """Attach variants to their products in one pass.

    Deliberately not a per-product query: with 35 products a naive loop would be
    36 round trips, and the N+1 pattern is the first thing that bites when this
    moves to a real database.
    """
    by_product: dict[str, list[dict]] = {}
    for v in variant_rows:
        by_product.setdefault(v["product_id"], []).append(
            {"size": v["size"], "stock_qty": v["stock_qty"]}
        )

    products = []
    for r in rows:
        p = dict(r)
        p["ships_international"] = bool(p["ships_international"])
        p["variants"] = by_product.get(p["id"], [])
        p["style"] = Style.WESTERN if p["category"] in WESTERN_CATEGORIES else Style.EASTERN
        products.append(p)
    return products


def _fetch_products(where: str = "", params: tuple = ()) -> list[dict]:
    conn = connect()
    try:
        rows = conn.execute(f"SELECT * FROM products {where} ORDER BY id", params).fetchall()
        if not rows:
            return []
        ids = tuple(r["id"] for r in rows)
        placeholders = ",".join("?" * len(ids))
        variants = conn.execute(
            f"SELECT * FROM variants WHERE product_id IN ({placeholders}) ORDER BY rowid",
            ids,
        ).fetchall()
        return _rows_to_products(rows, variants)
    finally:
        conn.close()


def get_product(product_id: str) -> dict | None:
    """Full product plus its variants. `None` if the id is unknown, so the API
    layer can turn that into a 404 (edge case #13)."""
    products = _fetch_products("WHERE id = ?", (product_id,))
    return products[0] if products else None


def list_products(
    *,
    style: str | None = None,
    product_type: str | None = None,
    size: str | None = None,
    brand: str | None = None,
) -> list[dict]:
    """Browse query.

    Filtering happens in Python rather than SQL for `size`, because the rule is
    not a simple equality: **unstitched pieces are `Free Size`, stitched to the
    customer's measurements, so they satisfy any requested size.** Hiding them
    behind a size filter would suppress options that genuinely fit
    (PLAN.md decision #15). Expressing that in SQL would be less readable than
    expressing it here, and at this scale it costs nothing.
    """
    clauses, params = [], []

    if style == Style.EASTERN:
        clauses.append(f"category IN ({','.join('?' * len(EASTERN_CATEGORIES))})")
        params.extend(EASTERN_CATEGORIES)
    elif style == Style.WESTERN:
        clauses.append(f"category IN ({','.join('?' * len(WESTERN_CATEGORIES))})")
        params.extend(WESTERN_CATEGORIES)

    if product_type:
        clauses.append("product_type = ?")
        params.append(product_type)

    if brand:
        clauses.append("brand = ?")
        params.append(brand)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    products = _fetch_products(where, tuple(params))

    if size:
        products = [p for p in products if _has_size(p, size)]

    return products


def _has_size(product: dict, size: str) -> bool:
    if product["product_type"] == "unstitched":
        return any(v["stock_qty"] > 0 for v in product["variants"])
    return any(v["size"] == size and v["stock_qty"] > 0 for v in product["variants"])


def list_brands() -> list[dict]:
    """Brand filter options with counts, so the UI can show what each choice
    would actually yield rather than offering a dead end."""
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT brand AS name, COUNT(*) AS product_count "
            "FROM products GROUP BY brand ORDER BY brand"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_destination(name: str) -> dict | None:
    """`None` for an unknown destination; a row with `serviceable = 0` is a
    *different* case (edge #7) and must stay distinguishable from unknown."""
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM destinations WHERE name = ?", (name,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["serviceable"] = bool(d["serviceable"])
        d["is_international"] = d["zone"] not in DOMESTIC_ZONES
        return d
    finally:
        conn.close()


def list_destinations() -> list[dict]:
    """Populates the location picker.

    Unserviceable destinations are returned too, not filtered out. Letting a
    customer pick one and telling them plainly at the gate is better than
    silently hiding it and leaving them to discover the problem later.
    """
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT * FROM destinations ORDER BY serviceable DESC, zone, name"
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["serviceable"] = bool(d["serviceable"])
            d["is_international"] = d["zone"] not in DOMESTIC_ZONES
            out.append(d)
        return out
    finally:
        conn.close()


def stock_status(stock_qty: int) -> StockStatus:
    """Map a raw quantity to what the customer is shown.

    Raw quantity leaves the repository here and goes no further — it is
    inventory data, not customer data (PLAN.md decision #8).
    """
    if stock_qty <= 0:
        return StockStatus.OUT_OF_STOCK
    if stock_qty <= LOW_STOCK_THRESHOLD:
        return StockStatus.LOW_STOCK
    return StockStatus.IN_STOCK


def variant_for(product: dict, size: str) -> dict | None:
    """The stock row for a size.

    Unstitched products carry a single `Free Size` variant, so any requested
    size resolves to it — the same rule as the browse filter, kept in one place.
    """
    if product["product_type"] == "unstitched":
        return product["variants"][0] if product["variants"] else None
    return next((v for v in product["variants"] if v["size"] == size), None)


def create_restock_alert(product_id: str, size: str, email: str | None, now: datetime) -> bool:
    """Record demand for an out-of-stock variant.

    The point is capturing the signal that would otherwise walk out of the shop:
    a customer who wanted a specific size is worth more than an anonymous bounce.
    """
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO restock_alerts (product_id, size, email, created_at) "
            "VALUES (?, ?, ?, ?)",
            (product_id, size, email, now.isoformat()),
        )
        conn.commit()
        return True
    finally:
        conn.close()
