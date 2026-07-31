/**
 * Product page controller.
 *
 * Single job: **the only module that touches the DOM on this page.**
 *
 * The loop, in full:
 *
 *     event → mutate state → render(state) → HTML strings → innerHTML
 *
 * Handlers do exactly two things: `set()` and let the subscription call render.
 * No handler reads the DOM to discover the state, and no handler writes to the
 * DOM directly. Break that rule and the page starts drifting out of sync with
 * reality — the failure mode we chose vanilla JS in spite of, not in ignorance
 * of (PLAN.md §6).
 */

import * as api from "./api.js";
import { createStore, loadPreferences, savePreferences } from "./store.js";
import { esc, pkr, productTile } from "./format.js";

import { sizeSelector } from "./components/sizeSelector.js";
import { confidenceCard } from "./components/confidenceCard.js";
import { alternativesRail } from "./components/alternativesRail.js";

const pdp = document.getElementById("pdp");
const errorEl = document.getElementById("pdp-error");
const tile = document.getElementById("product-tile");
const brandEl = document.getElementById("product-brand");
const titleEl = document.getElementById("product-title");
const priceEl = document.getElementById("product-price");
const metaEl = document.getElementById("product-meta");
const sizesEl = document.getElementById("size-selector");
const sizeHintEl = document.getElementById("size-hint");
const cardEl = document.getElementById("confidence-card");
const railEl = document.getElementById("alternatives-rail");

const store = createStore(
  {
    product: null,
    destinations: [],
    selectedSize: null,
    destination: null,
    destinationSource: "none", // "none" | "stored" | "user"
    arriveBy: null,
    confidence: null,
    alternatives: null, // null = never fetched; [] = fetched and empty
    railOpen: false,
    loadingConfidence: false,
    error: null,
  },
  render,
);

/** Guards against out-of-order responses: a slow request for "Karachi" must
 *  never overwrite a newer answer for "Lahore". */
let requestToken = 0;

const productId = () => new URLSearchParams(window.location.search).get("id");

// --------------------------------------------------------------------------
// Render — a flat list of assignments; components hold the branching
// --------------------------------------------------------------------------

function destinationControl(state) {
  const options = state.destinations
    .map(
      (d) =>
        `<option value="${esc(d.name)}" ${d.name === state.destination ? "selected" : ""}>` +
        `${esc(d.name)}${d.serviceable ? "" : " — not served yet"}</option>`,
    )
    .join("");

  // The badge is the honesty mechanism surfacing in the UI: a remembered city
  // is labelled as such until the customer confirms it on this page.
  const badge =
    state.destination && state.destinationSource === "stored"
      ? `<span class="badge is-estimated">remembered</span>`
      : "";

  return `
    <div class="dest-row">
      <select id="destination-select" aria-label="Delivery destination">
        <option value="">Select your city…</option>
        ${options}
      </select>
      ${badge}
    </div>`;
}

function deadlineControl(state) {
  // Label kept short on purpose: "Need it by a date? (optional)" was wide
  // enough to push the date field onto a second line inside the card.
  return `
    <label class="deadline" for="arrive-by">
      <span class="deadline__label">Need it by</span>
      <input type="date" id="arrive-by" value="${state.arriveBy || ""}"
             aria-label="Optional delivery deadline">
    </label>`;
}

function render(state) {
  if (state.error) {
    pdp.hidden = true;
    errorEl.hidden = false;
    errorEl.textContent = state.error;
    return;
  }
  if (!state.product) return;

  const p = state.product;
  pdp.hidden = false;

  tile.innerHTML = productTile(p, "pdp__tile");

  brandEl.textContent = p.brand;
  titleEl.textContent = p.title;
  priceEl.innerHTML =
    p.discount_pct > 0
      ? `${pkr(p.discounted_price_pkr)} <span class="card__was">${pkr(p.price_pkr)}</span>`
      : pkr(p.price_pkr);
  metaEl.textContent = [p.fabric, p.color, p.product_type === "unstitched" ? "Unstitched" : "Stitched"].join(" · ");

  sizesEl.innerHTML = sizeSelector(p.sizes, state.selectedSize);
  sizeHintEl.textContent =
    p.product_type === "unstitched"
      ? "Unstitched fabric — stitched to your measurements, so it fits any size."
      : "";

  cardEl.innerHTML = state.confidence
    ? confidenceCard(state.confidence, destinationControl(state), deadlineControl(state))
    : `<p class="loading">Checking availability…</p>`;

  railEl.hidden = !state.railOpen;
  if (state.railOpen) {
    railEl.innerHTML = state.alternatives
      ? alternativesRail(
          state.alternatives.items,
          state.alternatives.empty_reason,
          state.alternatives.filtered_on,
          state.selectedSize,
          state.confidence?.delivery?.reason,
          state.destination,
        )
      : `<p class="loading">Finding alternatives…</p>`;
  }
}

// --------------------------------------------------------------------------
// Data
// --------------------------------------------------------------------------

async function refreshConfidence() {
  const state = store.get();
  const token = ++requestToken;

  store.set({ loadingConfidence: true });
  try {
    const confidence = await api.fetchConfidence(state.product.id, {
      size: state.selectedSize,
      destination: state.destination,
      arriveBy: state.arriveBy,
    });
    if (token !== requestToken) return; // a newer request has already answered

    store.set({ confidence, loadingConfidence: false });

    // A failed check opens the rail on its own — recovery should not require
    // the customer to go looking for it.
    if (confidence.failed_checks.length) {
      store.set({ railOpen: true });
      refreshAlternatives();
    }
  } catch (error) {
    if (token === requestToken) store.set({ error: error.message, loadingConfidence: false });
  }
}

async function refreshAlternatives() {
  const state = store.get();
  store.set({ alternatives: null });
  try {
    const alternatives = await api.fetchAlternatives(state.product.id, {
      size: state.selectedSize,
      destination: state.destination,
      arriveBy: state.arriveBy,
    });
    store.set({ alternatives });
  } catch {
    store.set({ alternatives: { items: [], empty_reason: "Couldn't load alternatives.", filtered_on: [] } });
  }
}

// --------------------------------------------------------------------------
// Handlers — mutate state, nothing else
// --------------------------------------------------------------------------

sizesEl.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-size]");
  if (!button) return;
  // Sold-out sizes are tappable on purpose: the tap is intent worth answering,
  // not an invalid action to swallow (PLAN.md decision #6).
  const size = button.dataset.size;
  store.set({ selectedSize: size, railOpen: false });
  savePreferences({ size });
  refreshConfidence();
});

cardEl.addEventListener("change", (event) => {
  if (event.target.id === "destination-select") {
    const value = event.target.value || null;
    store.set({ destination: value, destinationSource: "user" });
    savePreferences({ city: value });
    refreshConfidence();
  }
  if (event.target.id === "arrive-by") {
    store.set({ arriveBy: event.target.value || null });
    refreshConfidence();
  }
});

cardEl.addEventListener("click", async (event) => {
  const target = event.target.closest("button");
  if (!target) return;

  // Both open the same rail. "deadline-alternatives" sits inside the deadline
  // verdict beside the date input, so the recovery is offered at the point the
  // problem is reported rather than only at the foot of the page.
  if (target.id === "view-alternatives" || target.id === "deadline-alternatives") {
    store.set({ railOpen: true });
    refreshAlternatives();
    railEl.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }

  if (target.id === "primary-cta") {
    const cta = target.dataset.cta;
    if (cta === "notify_me") {
      const state = store.get();
      // Email is intentionally not collected here: the flow works without PII,
      // and asking for it would need real consent handling (see README).
      await api.createRestockAlert(state.product.id, { size: state.selectedSize });
      target.textContent = "We'll let you know";
      target.disabled = true;
    } else if (cta === "see_alternatives") {
      store.set({ railOpen: true });
      refreshAlternatives();
      railEl.scrollIntoView({ behavior: "smooth", block: "start" });
    } else if (cta === "add_to_cart") {
      // Out of scope by design — the brief explicitly excludes checkout.
      target.textContent = "Added — checkout is out of scope";
      target.disabled = true;
    }
  }
});

async function init() {
  const id = productId();
  if (!id) {
    store.set({ error: "No product selected." });
    return;
  }

  const prefs = loadPreferences();

  try {
    const [product, destinations] = await Promise.all([
      api.fetchProduct(id),
      api.fetchDestinations(),
    ]);

    // A remembered city that no longer exists degrades to the cold-start state
    // rather than breaking the page (edge case #16).
    const known = destinations.some((d) => d.name === prefs.city);

    store.set({
      product,
      destinations,
      destination: known ? prefs.city : null,
      destinationSource: known ? "stored" : "none",
      // Only preselect a size this product actually offers.
      selectedSize: product.sizes.some((s) => s.size === prefs.size) ? prefs.size : null,
    });

    await refreshConfidence();
  } catch (error) {
    store.set({ error: error.message });
  }
}

init();
