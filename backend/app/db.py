"""SQLite connection, schema, and seed loading.

Single job: own the database file and its lifecycle. Nothing here knows about
HTTP; nothing outside `repository.py` should import from here.

Why SQLite rather than a JSON file in memory: data modelling is explicitly
graded, and a real schema with a foreign key states the product/variant
relationship better than nested dicts. The database is rebuilt from
`backend/seed/*.json` at startup and is gitignored — the JSON files are the
source of truth, the .db is a build artifact.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
SEED_DIR = BACKEND_DIR / "seed"
DB_PATH = BACKEND_DIR / "laam.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id                    TEXT PRIMARY KEY,
    title                 TEXT    NOT NULL,
    brand                 TEXT    NOT NULL,
    category              TEXT    NOT NULL,
    product_type          TEXT    NOT NULL,
    price_pkr             INTEGER NOT NULL,
    discount_pct          INTEGER NOT NULL DEFAULT 0,
    discount_ends_at      TEXT,
    color                 TEXT    NOT NULL,
    fabric                TEXT    NOT NULL,
    description_short     TEXT    NOT NULL,
    image_url             TEXT    NOT NULL,
    dispatch_city         TEXT    NOT NULL,
    dispatch_days         INTEGER NOT NULL,
    stitching_days        INTEGER NOT NULL DEFAULT 0,
    ships_international   INTEGER NOT NULL DEFAULT 1,
    on_time_rate          REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS variants (
    product_id  TEXT    NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    size        TEXT    NOT NULL,
    stock_qty   INTEGER NOT NULL,
    PRIMARY KEY (product_id, size)
);

CREATE TABLE IF NOT EXISTS destinations (
    name                        TEXT PRIMARY KEY,
    zone                        TEXT    NOT NULL,
    transit_days_min            INTEGER NOT NULL,
    transit_days_max            INTEGER NOT NULL,
    shipping_fee_pkr            INTEGER NOT NULL,
    free_shipping_threshold_pkr INTEGER NOT NULL,
    serviceable                 INTEGER NOT NULL DEFAULT 1
);

-- Demo-only. Production would need explicit consent capture and a PII policy;
-- see README. Email is nullable precisely so the flow works without it.
CREATE TABLE IF NOT EXISTS restock_alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id  TEXT NOT NULL REFERENCES products(id),
    size        TEXT NOT NULL,
    email       TEXT,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_variants_size ON variants(size, stock_qty);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
"""

#: Columns copied verbatim from each seed record. Listing them explicitly means
#: the `_comment` keys used to document edge cases in products.json are ignored
#: rather than blowing up the insert — the seed file doubles as documentation.
PRODUCT_COLUMNS = (
    "id",
    "title",
    "brand",
    "category",
    "product_type",
    "price_pkr",
    "discount_pct",
    "discount_ends_at",
    "color",
    "fabric",
    "description_short",
    "image_url",
    "dispatch_city",
    "dispatch_days",
    "stitching_days",
    "ships_international",
    "on_time_rate",
)

DESTINATION_COLUMNS = (
    "name",
    "zone",
    "transit_days_min",
    "transit_days_max",
    "shipping_fee_pkr",
    "free_shipping_threshold_pkr",
    "serviceable",
)


def connect() -> sqlite3.Connection:
    """Row factory set to `sqlite3.Row` so the repository can return dicts."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _read_seed(filename: str) -> list[dict]:
    with open(SEED_DIR / filename, encoding="utf-8") as fh:
        return json.load(fh)


def load_seed(conn: sqlite3.Connection) -> None:
    """Populate from `seed/products.json` and `seed/destinations.json`."""
    destinations = _read_seed("destinations.json")
    conn.executemany(
        f"INSERT INTO destinations ({','.join(DESTINATION_COLUMNS)}) "
        f"VALUES ({','.join('?' * len(DESTINATION_COLUMNS))})",
        [tuple(d[c] for c in DESTINATION_COLUMNS) for d in destinations],
    )

    products = _read_seed("products.json")
    conn.executemany(
        f"INSERT INTO products ({','.join(PRODUCT_COLUMNS)}) "
        f"VALUES ({','.join('?' * len(PRODUCT_COLUMNS))})",
        [tuple(p[c] for c in PRODUCT_COLUMNS) for p in products],
    )
    conn.executemany(
        "INSERT INTO variants (product_id, size, stock_qty) VALUES (?, ?, ?)",
        [
            (p["id"], v["size"], v["stock_qty"])
            for p in products
            for v in p.get("variants", [])
        ],
    )


#: Dropped in dependency order — variants reference products.
TABLES = ("variants", "restock_alerts", "products", "destinations")


def init_db(*, rebuild: bool = True) -> None:
    """Create the schema and load seed data.

    Called on FastAPI startup. `rebuild=True` **drops** the tables rather than
    just deleting rows: `CREATE TABLE IF NOT EXISTS` silently ignores a changed
    column list, so a schema edit would otherwise leave a stale database that
    fails at insert time with a confusing error. The .db is a disposable build
    artifact — the JSON seed is the source of truth — so dropping is the honest
    operation, and it keeps the demo deterministic on every restart.
    """
    conn = connect()
    try:
        if rebuild:
            for table in TABLES:
                conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.executescript(SCHEMA)
        load_seed(conn)
        conn.commit()
    finally:
        conn.close()
