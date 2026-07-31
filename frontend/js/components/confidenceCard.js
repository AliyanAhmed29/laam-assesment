/**
 * The confidence card — three facts folded into one decision.
 *
 * Pure function: `state → HTML string`.
 *
 * Ordered the way a person actually decides:
 *   your size → arrives when → you'll pay exactly this → act.
 *
 * **This component has a kill condition** (PLAN.md §10). If it degrades into
 * merely restating facts visible elsewhere on the page, it is a second place
 * saying the same thing and should be deleted. It earns its place by doing
 * three things nothing else can:
 *
 *   1. producing a single verdict — ready / blocked / incomplete;
 *   2. owning the unresolved prompts, so empty rows form a short action ladder
 *      rather than a dead panel;
 *   3. driving the CTA, so the button can never disagree with the rows above it.
 *
 * The CTA text comes from the server's `cta` field rather than being decided
 * here — that is what guarantees (3).
 */

import { esc } from "./../format.js";
import { priceBreakdown } from "./priceBreakdown.js";
import { deliveryPanel } from "./deliveryPanel.js";

const MARKS = { ok: "✓", fail: "✕", unresolved: "•" };
const CLASSES = { ok: "is-ok", fail: "is-failed", unresolved: "is-unresolved" };

const CTA_LABELS = {
  add_to_cart: "Add to cart",
  notify_me: "Notify me when it's back",
  see_alternatives: "See what else works",
  select_size: "Select a size",
};

/**
 * @param {object} confidence   A `ConfidenceResponse` from the API.
 * @param {string} destinationControl  Pre-rendered city selector markup.
 * @param {string} deadlineControl     Pre-rendered arrive-by input markup.
 */
export function confidenceCard(confidence, destinationControl, deadlineControl) {
  const check = (id) => confidence.checks.find((c) => c.id === id);

  return `
    <div class="conf__section">
      <p class="conf__label">Your size</p>
      ${checkRow(check("size"))}
    </div>

    ${deliveryPanel(
      confidence.delivery,
      check("delivery"),
      destinationControl + deadlineControl,
      Boolean(confidence.arrive_by),
    )}
    ${priceBreakdown(confidence.price)}

    <div class="conf__section conf__actions">
      ${ctaButton(confidence.cta, confidence.verdict)}
      <button class="link-btn" type="button" id="view-alternatives">View alternatives</button>
    </div>`;
}

/**
 * One check row.
 *
 * Unresolved rows are not failures and must not read like them — they carry a
 * prompt, because on a cold start the page is incomplete, not broken.
 */
function checkRow(check) {
  if (!check) return "";
  return `
    <p class="check ${CLASSES[check.status]}">
      <span class="check__mark">${MARKS[check.status]}</span>
      <span>${esc(check.label)}</span>
    </p>
    ${check.detail ? `<p class="check__detail">${esc(check.detail)}</p>` : ""}`;
}

/** The action. `select_size` is deliberately inert — it names the next step
 *  without pretending to be a thing you can usefully press yet. */
function ctaButton(cta, verdict) {
  const inert = cta === "select_size";
  return `
    <button class="btn" type="button" id="primary-cta"
            data-cta="${esc(cta)}" ${inert ? "disabled" : ""}>
      ${esc(CTA_LABELS[cta] || "Continue")}
    </button>`;
}
