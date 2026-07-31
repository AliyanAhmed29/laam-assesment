/**
 * Price breakdown — "What will I actually pay?" answered line by line.
 *
 * Pure function: `state → HTML string`.
 *
 * Renders the server's numbers verbatim. It never adds anything up: the moment
 * a client recomputes a total it can disagree with checkout.
 *
 * Three honesty rules it enforces:
 *
 *   - Before a city is known, delivery and total are shown as **ranges**, not
 *     placeholders and not point estimates. A range announces itself as a range.
 *   - GST is printed as a component of the total, never added to it — Pakistani
 *     retail prices are tax-inclusive, so adding 18% would manufacture the very
 *     surprise this page promises to prevent.
 *   - An inactive discount shows the list price with **no strikethrough**.
 */

import { esc, pkr, pkrRange } from "./../format.js";

/** @param {object} price A `PriceBreakdown` from the API. */
export function priceBreakdown(price) {
  const rows = [];

  rows.push(row("Item price", pkr(price.list_price_pkr)));

  if (price.discount_active) {
    rows.push(row(`Discount (${price.discount_pct}%)`, `−${pkr(price.discount_amount_pkr)}`));
    rows.push(row("Subtotal", pkr(price.subtotal_pkr)));
  }

  rows.push(deliveryRow(price));
  rows.push(totalRow(price));

  return `
    <div class="conf__section">
      <p class="conf__label">What you'll pay</p>
      ${rows.join("")}
      ${notes(price)}
    </div>`;
}

function row(label, value, className = "") {
  return `
    <div class="price-row">
      <span class="price-row__label">${esc(label)}</span>
      <span class="${className}">${value}</span>
    </div>`;
}

/**
 * Resolved: one exact figure. Unresolved: two ranges, because "free within
 * Pakistan / Rs 1,900–4,200 international" is two useful facts, whereas a
 * single band spanning both would be uselessly wide.
 */
function deliveryRow(price) {
  // We know where they are and cannot ship there. Quoting any delivery figure
  // would contradict the panel directly above this one.
  if (!price.deliverable) {
    return row("Delivery", "Not available here", "is-failed");
  }

  if (price.shipping_fee_pkr !== null && price.shipping_fee_pkr !== undefined) {
    return row("Delivery", pkr(price.shipping_fee_pkr));
  }

  const parts = [];
  if (price.domestic_shipping_range) {
    parts.push(row("Delivery — within Pakistan", pkrRange(price.domestic_shipping_range), "is-estimated"));
  }
  if (price.international_shipping_range) {
    parts.push(row("Delivery — international", pkrRange(price.international_shipping_range), "is-estimated"));
  }
  return parts.join("");
}

function totalRow(price) {
  // Nothing to total. The item price is already the first row, so repeating it
  // under a "Total" heading would both duplicate the figure and imply a total
  // exists. The note below says why there isn't one.
  if (!price.deliverable) return "";

  const resolved = price.total_pkr !== null && price.total_pkr !== undefined;
  return `
    <div class="price-row price-row--total">
      <span class="price-row__label">${resolved ? "Total" : "Total — estimated"}</span>
      <span class="${resolved ? "" : "is-estimated"}">
        ${resolved ? pkr(price.total_pkr) : pkrRange(price.total_range)}
      </span>
    </div>`;
}

function notes(price) {
  const out = [];

  if (!price.deliverable) {
    out.push(`<p class="price-note is-failed">We can't deliver this to your location, so there's no total to show.</p>`);
  } else if (price.total_pkr === null || price.total_pkr === undefined) {
    out.push(`<p class="price-note is-estimated">Select your city above for the exact total.</p>`);
  }

  // Genuinely useful information — how close they are to free delivery — rather
  // than a nudge dressed up as one.
  if (price.amount_to_free_shipping_pkr) {
    out.push(
      `<p class="price-note">Add ${pkr(price.amount_to_free_shipping_pkr)} more for free delivery.</p>`,
    );
  }

  if (price.gst_pkr) {
    out.push(
      `<p class="price-note price-note--gst">Includes ${pkr(price.gst_pkr)} GST ` +
        `(${price.gst_rate_pct}%) — already in the price, not added on top.</p>`,
    );
  }

  if (price.duties_note) {
    out.push(`<p class="price-note price-note--gst">${esc(price.duties_note)}</p>`);
  }

  return out.join("");
}
