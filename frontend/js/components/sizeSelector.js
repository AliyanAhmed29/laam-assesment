/**
 * Size chips.
 *
 * Pure function: `state → HTML string`. No fetch, no DOM, no state of its own.
 *
 * The one unconventional decision on the page lives here. **Sold-out sizes are
 * marked but remain tappable.** Disabling them is the industry default and it
 * is a dead end: the customer learns nothing and leaves. Tapping a struck-
 * through chip is a deliberate act meaning "M is the size I want" — a demand
 * signal worth answering with a recovery rather than swallowing.
 *
 * Because that interaction is unusual, the chip carries an explicit label
 * rather than relying on the customer to guess it is tappable.
 */

import { esc } from "./../format.js";

/**
 * @param {object[]} sizes     `[{ size, status, units_left }]`
 * @param {string|null} selected
 */
export function sizeSelector(sizes, selected) {
  return sizes.map((entry) => chip(entry, entry.size === selected)).join("");
}

/**
 * One chip.
 *
 * Honest scarcity only: `units_left` is shown when it is genuinely low, with no
 * countdown timer and no "12 people are viewing this".
 */
function chip(entry, isSelected) {
  const sold = entry.status === "out_of_stock";
  const low = entry.status === "low_stock";

  const note = sold
    ? `<small>tap for options</small>`
    : low
      ? `<small>${entry.units_left} left</small>`
      : "";

  return `
    <button type="button"
            class="size-chip ${sold ? "size-chip--sold" : ""}"
            data-size="${esc(entry.size)}"
            aria-pressed="${isSelected}"
            aria-label="${esc(entry.size)}${sold ? " — sold out, tap for alternatives" : ""}">
      <span>${esc(entry.size)}</span>${note}
    </button>`;
}
