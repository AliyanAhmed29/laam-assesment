"""Seed data generator.

Run:  python seed/generate.py      (from the backend/ directory)

The seed is a **design artifact, not filler**. Every row of the edge-case
register in PLAN.md §11 has a product below engineered to trigger it, and each
one says so in its `_comment`. The generator is committed so that intent stays
readable — a reviewer can see *why* the data looks the way it does instead of
inferring it from 30 anonymous JSON objects.

Generated products are deterministic (no RNG), so the demo is identical on every
machine and the README can safely name specific products and dates.
"""

from __future__ import annotations

import json
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent
OUT = SEED_DIR / "products.json"
IMAGES_MANIFEST = SEED_DIR / "images.json"

#: Used when no downloaded imagery is available. The frontend falls back to a
#: tinted tile showing `description_short`, so the app stays fully usable with
#: no images at all — `fetch_images.py` is optional, not a prerequisite.
PLACEHOLDER = "/img/placeholder.svg"


def load_images() -> dict[str, list[str]]:
    """Category -> image paths, from `fetch_images.py`.

    Absent manifest is a supported state, not an error: a reviewer who never
    runs the fetcher still gets a working app with text tiles.
    """
    if not IMAGES_MANIFEST.exists():
        return {}
    manifest = json.loads(IMAGES_MANIFEST.read_text(encoding="utf-8"))
    return {category: [r["file"] for r in records] for category, records in manifest.items()}

# --------------------------------------------------------------------------
# Edge-case archetypes — hand-written, each one earns its place
# --------------------------------------------------------------------------

EDGE_CASES: list[dict] = [
    {
        "_comment": "Baseline pret. Size M sold out so the primary failure→recovery path (edge #2) is reachable from the very first product.",
        "id": "noor-embroidered-lawn-3pc-teal",
        "title": "Embroidered Lawn 3-Piece — Teal",
        "brand": "Noor Studio",
        "category": "pret",
        "product_type": "ready_to_wear",
        "price_pkr": 8900,
        "discount_pct": 15,
        "discount_ends_at": "2026-08-20T23:59:00",
        "color": "Teal",
        "fabric": "Lawn",
        "description_short": "Teal embroidered lawn three-piece",
        "dispatch_city": "Lahore",
        "dispatch_days": 2,
        "stitching_days": 0,
        "ships_international": True,
        "on_time_rate": 0.94,
        "variants": [("XS", 4), ("S", 7), ("M", 0), ("L", 2), ("XL", 5)],
    },
    {
        "_comment": "EDGE #3 — every size sold out. The page is blocked entirely and the alternatives rail is the only way forward.",
        "id": "laalzari-luxury-pret-maroon",
        "title": "Luxury Pret Kameez — Maroon",
        "brand": "Laalzari",
        "category": "pret",
        "product_type": "ready_to_wear",
        "price_pkr": 11500,
        "discount_pct": 0,
        "discount_ends_at": None,
        "color": "Maroon",
        "fabric": "Silk",
        "description_short": "Maroon silk luxury kameez",
        "dispatch_city": "Lahore",
        "dispatch_days": 2,
        "stitching_days": 0,
        "ships_international": True,
        "on_time_rate": 0.90,
        "variants": [("XS", 0), ("S", 0), ("M", 0), ("L", 0), ("XL", 0)],
    },
    {
        "_comment": "EDGE #4 — low stock throughout, exercising honest scarcity ('Only 2 left') with no countdown timers or view-counters.",
        "id": "bagh-handloom-kurta-indigo",
        "title": "Handloom Kurta — Indigo",
        "brand": "Bagh",
        "category": "pret",
        "product_type": "ready_to_wear",
        "price_pkr": 5400,
        "discount_pct": 0,
        "discount_ends_at": None,
        "color": "Indigo",
        "fabric": "Khaddar",
        "description_short": "Indigo handloom khaddar kurta",
        "dispatch_city": "Multan",
        "dispatch_days": 3,
        "stitching_days": 0,
        "ships_international": True,
        "on_time_rate": 0.85,
        "variants": [("S", 1), ("M", 2), ("L", 3), ("XL", 1)],
    },
    {
        "_comment": "EDGE #5 — unstitched. Free Size only, and 6 stitching days push the arrival window out. The one piece of genuine LAAM domain knowledge in the build.",
        "id": "kohinoor-unstitched-3pc-emerald",
        "title": "Unstitched Embroidered 3-Piece — Emerald",
        "brand": "Kohinoor Pret",
        "category": "unstitched",
        "product_type": "unstitched",
        "price_pkr": 6800,
        "discount_pct": 20,
        "discount_ends_at": "2026-08-15T23:59:00",
        "color": "Emerald",
        "fabric": "Chiffon",
        "description_short": "Emerald unstitched chiffon three-piece",
        "dispatch_city": "Faisalabad",
        "dispatch_days": 2,
        "stitching_days": 6,
        "ships_international": True,
        "on_time_rate": 0.89,
        "variants": [("Free Size", 25)],
    },
    {
        "_comment": "EDGE #6 — discount expired 10 July. Must fall back to list price with NO strikethrough; a fake 'was' price is the dishonesty this build argues against.",
        "id": "noor-formal-gharara-gold",
        "title": "Formal Gharara Set — Gold",
        "brand": "Noor Studio",
        "category": "formals",
        "product_type": "ready_to_wear",
        "price_pkr": 32000,
        "discount_pct": 25,
        "discount_ends_at": "2026-07-10T23:59:00",
        "color": "Gold",
        "fabric": "Jamawar",
        "description_short": "Gold jamawar formal gharara",
        "dispatch_city": "Lahore",
        "dispatch_days": 3,
        "stitching_days": 0,
        "ships_international": True,
        "on_time_rate": 0.87,
        "variants": [("S", 2), ("M", 3), ("L", 1)],
    },
    {
        "_comment": "EDGE #8 — brand ships domestically only. Must yield a reason distinct from an unserviceable city, because the recovery differs: here we can offer brands that DO ship abroad.",
        "id": "meher-bridal-lehnga-crimson",
        "title": "Bridal Lehnga — Crimson",
        "brand": "Meher",
        "category": "formals",
        "product_type": "ready_to_wear",
        "price_pkr": 145000,
        "discount_pct": 0,
        "discount_ends_at": None,
        "color": "Crimson",
        "fabric": "Velvet",
        "description_short": "Crimson velvet bridal lehnga",
        "dispatch_city": "Lahore",
        "dispatch_days": 5,
        "stitching_days": 0,
        "ships_international": False,
        "on_time_rate": 0.82,
        "variants": [("S", 1), ("M", 1), ("L", 0)],
    },
    {
        "_comment": "Western wear with S and M sold out, so the failure path is reachable outside eastern categories too. NOTE: this was originally intended to demo the empty rail (edge #11), but the generated filler below supplies enough western pieces that alternatives now exist — which is the correct outcome. Edge #11 is instead exercised by an unreachable arrive_by deadline (e.g. Canada by 10 Aug), where no product in the catalogue can pass the hard filter.",
        "id": "zaria-west-co-ord-charcoal",
        "title": "Co-ord Set — Charcoal",
        "brand": "Zaria",
        "category": "west",
        "product_type": "ready_to_wear",
        "price_pkr": 13800,
        "discount_pct": 0,
        "discount_ends_at": None,
        "color": "Charcoal",
        "fabric": "Linen",
        "description_short": "Charcoal linen co-ord set",
        "dispatch_city": "Karachi",
        "dispatch_days": 2,
        "stitching_days": 0,
        "ships_international": True,
        "on_time_rate": 0.92,
        "variants": [("S", 0), ("M", 0), ("L", 2)],
    },
    {
        "_comment": "EDGE #19 — Rs 4,800 subtotal sits just under the Rs 5,000 free-delivery threshold, so the 'add Rs 200 for free delivery' hint has something real to report.",
        "id": "sarosh-cotton-kurta-mustard",
        "title": "Cotton Kurta — Mustard",
        "brand": "Sarosh",
        "category": "pret",
        "product_type": "ready_to_wear",
        "price_pkr": 4800,
        "discount_pct": 0,
        "discount_ends_at": None,
        "color": "Mustard",
        "fabric": "Cotton",
        "description_short": "Mustard cotton everyday kurta",
        "dispatch_city": "Karachi",
        "dispatch_days": 1,
        "stitching_days": 0,
        "ships_international": True,
        "on_time_rate": 0.95,
        "variants": [("XS", 6), ("S", 8), ("M", 10), ("L", 4), ("XL", 2)],
    },
]

# --------------------------------------------------------------------------
# Deterministic filler — gives the filters and the alternatives rail enough
# candidates to be meaningful. With only a dozen products the ranking function's
# quality is invisible, which would make it untestable in practice.
# --------------------------------------------------------------------------

BRANDS = [
    ("Noor Studio", "Lahore", 2, 0.94, True),
    ("Meher", "Lahore", 1, 0.97, True),
    ("Aab", "Karachi", 2, 0.91, True),
    ("Zaria", "Lahore", 3, 0.88, True),
    ("Laalzari", "Lahore", 2, 0.90, True),
    ("Bagh", "Multan", 3, 0.85, True),
    ("Kohinoor Pret", "Faisalabad", 2, 0.89, True),
    ("Sarosh", "Karachi", 1, 0.93, True),
]

# (category, product_type, fabric, base_price, noun)
ARCHETYPES = [
    ("pret", "ready_to_wear", "Lawn", 7200, "Lawn 3-Piece"),
    ("pret", "ready_to_wear", "Cotton", 5600, "Cotton Kurta"),
    ("pret", "ready_to_wear", "Khaddar", 6400, "Khaddar Suit"),
    ("formals", "ready_to_wear", "Chiffon", 26000, "Formal Chiffon Set"),
    ("formals", "ready_to_wear", "Organza", 34000, "Organza Formal"),
    ("unstitched", "unstitched", "Lawn", 4200, "Unstitched Lawn 3-Piece"),
    ("unstitched", "unstitched", "Cambric", 3900, "Unstitched Cambric 2-Piece"),
    ("west", "ready_to_wear", "Linen", 9800, "Linen Shirt Dress"),
    ("west", "ready_to_wear", "Denim", 8200, "Denim Jacket"),
]

COLORS = ["Ivory", "Rose", "Sage", "Navy", "Black", "Blush", "Olive", "Rust", "Plum"]

#: Cycled so stock varies predictably: some full, some low, some partly sold out.
STOCK_PATTERNS = [
    [6, 9, 12, 7, 3],
    [0, 5, 8, 3, 0],
    [2, 2, 4, 1, 0],
    [11, 14, 16, 9, 6],
    [3, 0, 7, 5, 2],
]

SIZES = ["XS", "S", "M", "L", "XL"]


def slug(*parts: str) -> str:
    return "-".join(p.lower().replace(" ", "-").replace("—", "").strip("-") for p in parts)


def build_filler() -> list[dict]:
    products: list[dict] = []
    for i, (category, ptype, fabric, base, noun) in enumerate(ARCHETYPES):
        # Two brands per archetype keeps every category populated across brands,
        # so the brand filter never produces a near-empty grid.
        for j in range(3):
            brand, city, dispatch, on_time, intl = BRANDS[(i * 3 + j) % len(BRANDS)]
            color = COLORS[(i * 3 + j) % len(COLORS)]
            price = base + (j * 900) - (i * 120)
            discount = [0, 10, 20][(i + j) % 3]

            if ptype == "unstitched":
                variants = [("Free Size", 20 + j * 7)]
                stitching = 5 + (j % 3)
            else:
                pattern = STOCK_PATTERNS[(i + j) % len(STOCK_PATTERNS)]
                variants = list(zip(SIZES, pattern))
                stitching = 0

            products.append(
                {
                    "id": slug(brand, noun, color),
                    "title": f"{noun} — {color}",
                    "brand": brand,
                    "category": category,
                    "product_type": ptype,
                    "price_pkr": price,
                    "discount_pct": discount,
                    "discount_ends_at": "2026-09-30T23:59:00" if discount else None,
                    "color": color,
                    "fabric": fabric,
                    "description_short": f"{color} {fabric.lower()} {noun.lower()}",
                    "dispatch_city": city,
                    "dispatch_days": dispatch,
                    "stitching_days": stitching,
                    "ships_international": intl,
                    "on_time_rate": on_time,
                    "variants": variants,
                }
            )
    return products


def normalise(product: dict, image_url: str) -> dict:
    """Expand the compact `(size, qty)` tuples into the JSON shape."""
    out = dict(product)
    out["image_url"] = image_url
    out["variants"] = [{"size": s, "stock_qty": q} for s, q in product["variants"]]
    return out


def main() -> None:
    images = load_images()
    cursors: dict[str, int] = {}

    def next_image(category: str) -> str:
        """Rotate through the images for a category.

        There are fewer photographs than products, so some are reused. Assigning
        round-robin rather than randomly keeps the output deterministic — the
        README can name a specific product and a reviewer sees the same thing.
        """
        pool = images.get(category) or []
        if not pool:
            return PLACEHOLDER
        index = cursors.get(category, 0)
        cursors[category] = index + 1
        return pool[index % len(pool)]

    seen: set[str] = set()
    products: list[dict] = []
    for p in EDGE_CASES + build_filler():
        if p["id"] in seen:
            continue  # edge cases win; a filler collision is silently dropped
        seen.add(p["id"])
        products.append(normalise(p, next_image(p["category"])))

    OUT.write_text(json.dumps(products, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(products)} products -> {OUT}")

    brands = sorted({p["brand"] for p in products})
    cats = sorted({p["category"] for p in products})
    print(f"  brands:     {len(brands)} — {', '.join(brands)}")
    print(f"  categories: {', '.join(cats)}")
    sold_out = [p["id"] for p in products if all(v["stock_qty"] == 0 for v in p["variants"])]
    print(f"  fully sold out: {sold_out}")


if __name__ == "__main__":
    main()
