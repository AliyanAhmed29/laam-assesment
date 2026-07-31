/**
 * Delivery panel — "Can I trust the delivery promise?"
 *
 * Pure function: `state → HTML string`.
 *
 * Renders a **window**, never a single date, and can show its working: the
 * step-by-step breakdown turns the promise into something a customer can audit
 * rather than take on faith. That breakdown is collapsed by default — available
 * on demand, without costing ~200px of card height to everyone who never asks.
 *
 * **Severity comes from the server's check, not from re-reading `delivery`.**
 * The panel used to derive its own status from `delivery.available`, which meant
 * a missed deadline still rendered a green tick with the arrival window: the
 * estimate existed, it just landed too late. The only visible signal was the
 * alternatives heading far below. Now the check drives it, so a failure appears
 * directly beneath the date input that caused it.
 */

import { esc, onTimeLabel, shortDate } from "./../format.js";

/**
 * Reasons that are *waiting on the customer* rather than failures.
 *
 * `out_of_stock` belongs here even though no estimate exists: the sold-out size
 * already has its own red row above, and painting a second one would show two
 * problems where there is one.
 */
const PROMPT_REASONS = ["no_destination", "out_of_stock", "no_size_selected"];

const REASON_COPY = {
  no_destination: "Select your city to see delivery dates",
  out_of_stock: "Delivery shown once a size is available",
  not_serviceable: "We don't deliver to this location yet",
  brand_no_international: "This brand ships within Pakistan only",
  no_size_selected: "Select a size to see delivery dates",
};

/**
 * @param {object} delivery       A `DeliveryEstimate` from the API.
 * @param {object} check          The server's `delivery` check — owns severity.
 * @param {string} controls       Pre-rendered city selector + deadline input.
 * @param {boolean} hasDeadline   Whether the customer set an arrive-by date.
 */
export function deliveryPanel(delivery, check, controls, hasDeadline) {
  return `
    <div class="conf__section">
      <p class="conf__label">Delivery</p>
      ${controls}
      ${body(delivery, check, hasDeadline)}
    </div>`;
}

function body(delivery, check, hasDeadline) {
  // Estimate exists but misses the deadline. This is the case that has to sit
  // next to the date field — it is a direct answer to what was just typed.
  if (delivery.available && check?.status === "fail") {
    return `
      ${deadlineVerdict("is-failed", "✕", check.label, "See what arrives in time")}
      ${window_(delivery, true)}
      ${why(delivery)}`;
  }

  if (delivery.available) {
    return `
      ${hasDeadline ? deadlineVerdict("is-ok", "✓", "Arrives in time", null) : ""}
      ${window_(delivery, false)}
      ${why(delivery)}
      ${delivery.on_time_rate ? `<p class="price-note">${esc(onTimeLabel(delivery.on_time_rate))}</p>` : ""}`;
  }

  const isPrompt = PROMPT_REASONS.includes(delivery.reason);
  return `
    <p class="check ${isPrompt ? "is-unresolved" : "is-failed"}">
      <span class="check__mark">${isPrompt ? "•" : "✕"}</span>
      <span>${esc(REASON_COPY[delivery.reason] || "Delivery estimate unavailable")}</span>
    </p>
    ${delivery.dispatch_note ? `<p class="check__detail">${esc(delivery.dispatch_note)}</p>` : ""}`;
}

/** The boxed answer to the arrive-by question, rendered inline with the input. */
function deadlineVerdict(className, mark, label, actionLabel) {
  const action = actionLabel
    ? `<button type="button" class="deadline__verdict-action" id="deadline-alternatives">${esc(actionLabel)}</button>`
    : "";
  return `
    <p class="deadline__verdict ${className}">
      <span class="check__mark">${mark}</span>
      <span>${esc(label)}${action}</span>
    </p>`;
}

function window_(delivery, muted) {
  const range =
    delivery.arrives_from === delivery.arrives_to
      ? shortDate(delivery.arrives_to)
      : `${shortDate(delivery.arrives_from)} – ${shortDate(delivery.arrives_to)}`;

  // When the deadline already failed above, the window is context rather than a
  // second verdict — so it loses the tick and the green.
  return muted
    ? `<p class="check__detail">Estimated arrival ${esc(range)}</p>`
    : `<p class="check is-ok"><span class="check__mark">✓</span><span>Arrives ${esc(range)}</span></p>`;
}

/** "Why this date?" — dispatch, stitching, transit, and the days skipped. */
function why(delivery) {
  if (!delivery.steps?.length) return "";

  const steps = delivery.steps
    .map(
      (s) =>
        `<li><span>${esc(s.label)}</span><span>${s.days} ${s.days === 1 ? "day" : "days"}</span></li>`,
    )
    .join("");

  const skipped = delivery.skipped_dates?.length
    ? `<li><span>Closed on ${delivery.skipped_dates.map(shortDate).join(", ")}</span><span></span></li>`
    : "";

  return `
    <details class="why">
      <summary>Why this date?</summary>
      <ul class="steps">${steps}${skipped}</ul>
    </details>`;
}
