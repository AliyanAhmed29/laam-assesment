/**
 * Alternatives rail — the recovery path.
 *
 * Pure function: `state → HTML string`.
 *
 * Two triggers, one mechanism: the customer presses "View alternatives", or a
 * check fails and the rail opens automatically, hard-filtered by whatever went
 * wrong. That is why the heading names the problem before offering the fix.
 *
 * Every card states **why it is on screen** — "In stock in M · Same fabric ·
 * Rs 800 less". Those labels come from the server's `reasons[]`, so a card can
 * never claim something the ranking did not actually check. It is the entire
 * difference between a recommender and a confidence tool.
 *
 * When nothing qualifies it says so plainly. Padding the rail with irrelevant
 * products would undo the honesty the rest of the page is built on.
 */

import { esc, pkr, productTile } from "./../format.js";

/**
 * @param {object[]} items
 * @param {string|null} emptyReason
 * @param {string[]} filteredOn  Which failed constraints drove the filter.
 * @param {string|null} size
 */
export function alternativesRail(items, emptyReason, filteredOn, size, deliveryReason, city) {
  return `
    <h2 class="rail__heading">${esc(headingFor(filteredOn, size, deliveryReason, city))}</h2>
    <p class="rail__sub">${esc(subFor(filteredOn, items.length, deliveryReason))}</p>
    ${items.length ? `<div class="grid">${items.map(card).join("")}</div>` : emptyState(emptyReason)}`;
}

/**
 * Names the problem before offering the fix.
 *
 * `filteredOn` only carries check *ids*, and the delivery check fails for
 * several genuinely different reasons — an unserviceable city is not the same
 * problem as a missed deadline. Collapsing them into one heading would tell the
 * customer something untrue, so the specific reason is passed in alongside.
 */
function headingFor(filteredOn, size, deliveryReason, city) {
  if (filteredOn.includes("size")) {
    return size ? `Size ${size} is sold out` : "This piece is sold out";
  }
  if (filteredOn.includes("delivery")) {
    const where = city ? ` to ${city}` : "";
    if (deliveryReason === "brand_no_international") return `This brand doesn't ship${where}`;
    if (deliveryReason === "not_serviceable") return `We don't deliver${where} yet`;
    return "This one won't arrive in time";
  }
  return "Similar pieces";
}

function subFor(filteredOn, count, deliveryReason) {
  if (!count) return "";
  if (filteredOn.includes("size")) {
    return `${count} similar ${count === 1 ? "piece" : "pieces"} you can actually get.`;
  }
  if (filteredOn.includes("delivery")) {
    return deliveryReason && deliveryReason !== "no_destination"
      ? `${count} that can reach you.`
      : `${count} that can reach you in time.`;
  }
  return `${count} that would do a similar job.`;
}

function card(item) {
  return `
    <a class="card" href="/product.html?id=${encodeURIComponent(item.id)}">
      ${productTile(item, "card__tile")}
      <p class="card__brand">${esc(item.brand)}</p>
      <p class="card__title">${esc(item.title)}</p>
      <p class="card__price">${pkr(item.discounted_price_pkr)}</p>
      <ul class="rail__reasons">
        ${item.reasons.map((r) => `<li>${esc(r)}</li>`).join("")}
      </ul>
    </a>`;
}

/** The honest empty state. */
function emptyState(emptyReason) {
  return `<p class="empty">${esc(emptyReason || "Nothing similar right now.")}</p>`;
}
