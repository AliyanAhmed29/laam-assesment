"""Download openly-licensed product imagery.

Run:  python seed/fetch_images.py      (from the backend/ directory)

Why not LAAM's own product photos
---------------------------------
LAAM's catalogue images are copyrighted by LAAM and its brands, and nothing in
their robots.txt grants a licence to copy and redistribute them. There is also a
product reason: every brand in this seed is **invented** precisely so that no
real company has fabricated stock, pricing or delivery data attributed to it
(see README §4). Pinning real photographs of real garments onto invented brands
would undo that.

So this pulls from **Openverse**, the Creative Commons image index, and keeps
only permissively licensed files. Attribution for every image is written to
`frontend/img/products/ATTRIBUTION.md` — required for the `by` / `by-sa`
licences, and good manners for the rest.

These are honest *stand-ins*: real photographs of South Asian clothing, not
photographs of these specific fictional products. Swapping in real catalogue
shots later means replacing the files and re-running `generate.py`.
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent
IMG_DIR = SEED_DIR.parent.parent / "frontend" / "img" / "products"
MANIFEST = SEED_DIR / "images.json"
ATTRIBUTION = IMG_DIR / "ATTRIBUTION.md"

API = "https://api.openverse.org/v1/images/"
UA = "LAAM-assessment-demo/1.0 (educational take-home project)"

#: Licences that allow reuse. `nd` (no-derivatives) and `nc` (non-commercial)
#: variants are excluded — this is a commercial-shaped demo and we should not
#: pretend otherwise.
ALLOWED_LICENSES = {"cc0", "pdm", "by", "by-sa"}

#: Search terms per catalogue category. More terms than needed, because a lot of
#: CC results are documentary photographs rather than product shots.
QUERIES: dict[str, list[str]] = {
    "pret": [
        "shalwar kameez",
        "kurta women",
        "pakistani clothing",
        "salwar suit",
        "indian tunic dress",
    ],
    "formals": [
        "lehenga",
        "sari silk",
        "bridal south asian dress",
        "embroidered formal dress",
        "wedding dress india",
    ],
    "unstitched": [
        "block print textile",
        "embroidered fabric",
        "cotton textile roll",
        "silk fabric cloth",
        "handloom fabric",
    ],
    "west": [
        "linen dress",
        "denim jacket",
        "co-ord set fashion",
        "womens blouse",
        "casual dress clothing",
    ],
}

TARGET_PER_CATEGORY = 8

#: Photographers upload near-identical series ("Linen dress ... 2", "... 3"),
#: and taking them all produces a grid of the same garment nine times. Capping
#: per search term forces variety across the term list instead.
MAX_PER_TERM = 2

#: A demo has no business shipping a 6 MB hero image. Anything larger is skipped
#: rather than resized — adding Pillow just to shrink placeholder art would be a
#: dependency for nothing.
MAX_BYTES = 1_200_000


def get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=40) as response:
        return json.loads(response.read())


def search(term: str, page_size: int = 20) -> list[dict]:
    query = urllib.parse.urlencode(
        {"q": term, "page_size": page_size, "license_type": "all-cc", "mature": "false"}
    )
    try:
        return get_json(f"{API}?{query}").get("results", [])
    except Exception as exc:  # noqa: BLE001 — a dead search term must not abort the run
        print(f"    ! search failed for {term!r}: {exc}")
        return []


#: Wikimedia rejects arbitrary thumbnail widths with HTTP 400 — only a fixed set
#: of standard sizes is served. 640 is the smallest that still looks sharp in a
#: product tile on a high-DPI screen.
WIKIMEDIA_THUMB_WIDTH = 640


def resized_url(record: dict) -> str:
    """Prefer a resized copy over a multi-megabyte original.

    Most Openverse CC results are hosted on Wikimedia, which exposes a
    predictable `/thumb/<path>/<width>px-<name>` form. Openverse's own thumbnail
    endpoint exists but 424s often enough that it is not worth depending on.
    """
    url = record["url"]
    match = re.match(r"(https://upload\.wikimedia\.org/wikipedia/commons)/(\w+/\w{2})/(.+)$", url)
    if match and url.lower().endswith((".jpg", ".jpeg", ".png")):
        base, path, name = match.groups()
        return f"{base}/thumb/{path}/{name}/{WIKIMEDIA_THUMB_WIDTH}px-{name}"
    return url


def _fetch(url: str) -> bytes | None:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(request, timeout=60) as response:
            if not response.headers.get("Content-Type", "").startswith("image/"):
                return None
            data = response.read()
        if len(data) < 4_000:  # too small to be a usable photo
            return None
        return data if len(data) <= MAX_BYTES else None
    except Exception:  # noqa: BLE001
        return None


def download(record: dict, destination: Path) -> bool:
    """Try the resized copy, then fall back to the original.

    Wikimedia refuses a thumbnail wider than the source image, and serves only a
    fixed set of widths, so a fixed-width thumb URL fails for a meaningful share
    of results. Falling back to the original costs bandwidth but keeps those
    images rather than silently dropping them.
    """
    for url in dict.fromkeys([resized_url(record), record["url"]]):
        data = _fetch(url)
        if data:
            destination.write_bytes(data)
            return True
    return False


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:48] or "image"


def series_key(title: str) -> str:
    """Collapse a numbered series to one key.

    "Linen dress with reverse applique 4" and "... 7" are the same garment
    photographed twice. Without this the rail shows one dress nine times.
    """
    return re.sub(r"[-\s]*\d+$", "", slugify(title))[:34]


def collect() -> dict[str, list[dict]]:
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, list[dict]] = {}
    seen_ids: set[str] = set()
    seen_series: set[str] = set()
    used_filenames: set[str] = set()

    for category, terms in QUERIES.items():
        print(f"\n{category}:")
        chosen: list[dict] = []

        for term in terms:
            if len(chosen) >= TARGET_PER_CATEGORY:
                break
            taken_for_term = 0

            for record in search(term):
                if len(chosen) >= TARGET_PER_CATEGORY or taken_for_term >= MAX_PER_TERM:
                    break
                if record["id"] in seen_ids:
                    continue
                if record.get("license") not in ALLOWED_LICENSES:
                    continue
                if (record.get("width") or 0) < 400 or (record.get("height") or 0) < 400:
                    continue

                key = series_key(record.get("title") or record["id"])
                if key in seen_series:
                    continue

                # Distinct records can slugify to the same name. Without a
                # counter the second silently reuses the first one's file, and
                # the manifest ends up with duplicate images.
                stem = f"{category}-{slugify(record.get('title') or record['id'])}"
                filename = f"{stem}.jpg"
                suffix = 2
                while filename in used_filenames:
                    filename = f"{stem}-{suffix}.jpg"
                    suffix += 1
                destination = IMG_DIR / filename

                # A .png original still gets written to a .jpg filename;
                # browsers sniff content type, so this is cosmetic only.
                if download(record, destination):
                    used_filenames.add(filename)
                    seen_ids.add(record["id"])
                    seen_series.add(key)
                    taken_for_term += 1
                    chosen.append(
                        {
                            "file": f"/img/products/{filename}",
                            "title": record.get("title") or "Untitled",
                            "creator": record.get("creator") or "Unknown",
                            "license": record.get("license", ""),
                            "license_version": record.get("license_version", ""),
                            "license_url": record.get("license_url", ""),
                            "source": record.get("foreign_landing_url", ""),
                        }
                    )
                    print(f"  [ok] {filename}")
            time.sleep(0.4)  # be a considerate API client

        manifest[category] = chosen
        print(f"  -> {len(chosen)} images for {category}")

    return manifest


def write_attribution(manifest: dict[str, list[dict]]) -> None:
    lines = [
        "# Image attribution",
        "",
        "All imagery is openly licensed and was retrieved via the "
        "[Openverse](https://openverse.org) index by `backend/seed/fetch_images.py`.",
        "",
        "These are **stand-ins**: real photographs of South Asian clothing, not "
        "photographs of the fictional products in this demo. LAAM's own catalogue "
        "images are copyrighted and are deliberately not used.",
        "",
    ]
    for category, records in manifest.items():
        lines += [f"## {category}", ""]
        for r in records:
            licence = f"CC {r['license'].upper()} {r['license_version']}".strip()
            lines.append(
                f"- **{r['title']}** — {r['creator']} — "
                f"[{licence}]({r['license_url']}) — [source]({r['source']})"
            )
        lines.append("")
    ATTRIBUTION.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    manifest = collect()
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_attribution(manifest)

    total = sum(len(v) for v in manifest.values())
    print(f"\nwrote {total} images -> {IMG_DIR}")
    print(f"manifest    -> {MANIFEST}")
    print(f"attribution -> {ATTRIBUTION}")
    if total < sum(1 for _ in QUERIES):
        print("\nWARNING: very few images retrieved; products will fall back to text tiles.")


if __name__ == "__main__":
    main()
