/**
 * Display formatting.
 *
 * Single job: turn API values into strings a human reads. Pure functions, no
 * DOM, no state.
 *
 * Note what is *not* here: no price arithmetic and no date arithmetic. Those
 * come from the server or they do not appear at all. Recomputing them on the
 * client is how "price shown ≠ price charged" bugs are born (PLAN.md §14).
 */

/** 5480 → "Rs 5,480". Whole rupees — the API deals in integers. */
export function pkr(amount) {
  if (amount === null || amount === undefined) return "—";
  if (amount === 0) return "Free";
  return `Rs ${amount.toLocaleString("en-PK")}`;
}

/** A money range: "Free – Rs 4,200", or a single value when both ends match. */
export function pkrRange(range) {
  if (!range) return "—";
  if (range.min_pkr === range.max_pkr) return pkr(range.min_pkr);
  return `${pkr(range.min_pkr)} – ${pkr(range.max_pkr)}`;
}

/** "2026-08-08" → "Sat 8 Aug". Parsed as parts, not `new Date(string)`, which
 *  applies a timezone shift and can land a day early. */
export function shortDate(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-").map(Number);
  const date = new Date(y, m - 1, d);
  return date.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
}

/** "in_stock" → "In stock"; "low_stock" → "Only 2 left". */
export function stockLabel(status, unitsLeft) {
  if (status === "out_of_stock") return "Sold out";
  if (status === "low_stock") return unitsLeft ? `Only ${unitsLeft} left` : "Low stock";
  return "In stock";
}

/** 0.94 → "94% of this brand's orders arrive on time". */
export function onTimeLabel(rate) {
  if (!rate) return "";
  return `${Math.round(rate * 100)}% of this brand's orders arrive on time`;
}

/** Deterministic hue (0–359) from the product colour name.
 *
 *  Only the *hue* is decided here — saturation and lightness live in CSS as
 *  `--tile-s` / `--tile-l`, so the same tile reads correctly in both themes. An
 *  inline `hsl(...)` string could not do that, because inline styles cannot
 *  respond to a media query or a `data-theme` switch. */
export function tintHue(colorName) {
  let hash = 0;
  for (const ch of colorName || "") hash = (hash * 31 + ch.charCodeAt(0)) % 360;
  return hash;
}

/**
 * The product tile: a real photograph when one exists, otherwise the tinted
 * text tile.
 *
 * The fallback is not dead code. `seed/fetch_images.py` is optional, so a
 * reviewer who never runs it still gets a complete, legible catalogue rather
 * than a grid of broken-image icons. `onerror` covers the third case — a
 * manifest that references a file someone has since deleted.
 *
 * @param {object} product
 * @param {string} className  "card__tile" on the grid, "pdp__tile" on the PDP.
 */
export function productTile(product, className) {
  const hue = tintHue(product.color);
  const caption = esc(product.description_short);
  const hasPhoto = product.image_url && !product.image_url.endsWith("placeholder.svg");

  if (!hasPhoto) {
    return `<div class="${className}" style="--tile-h:${hue}"><span>${caption}</span></div>`;
  }

  return `
    <div class="${className} ${className}--photo" style="--tile-h:${hue}">
      <img src="${esc(product.image_url)}" alt="${caption}" loading="lazy"
           onerror="this.remove()">
      <span>${caption}</span>
    </div>`;
}

/** Escape interpolated values — every component builds HTML strings. */
export function esc(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch],
  );
}
