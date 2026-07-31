/**
 * Browse page controller.
 *
 * Single job: the only module that touches the DOM on the discovery page.
 * Same loop as product.js — handlers mutate state, one render draws from it.
 *
 * The four filters are the bridge between the two halves of the assessment
 * title: discovery that already carries the confidence signal, so a shopper is
 * not clicking into products that cannot serve them.
 */

import { fetchBrands, fetchProducts } from "./api.js";
import { createStore, loadPreferences, savePreferences, clearCity } from "./store.js";
import { esc, pkr, productTile } from "./format.js";

const grid = document.getElementById("product-grid");
const empty = document.getElementById("listing-empty");
const summary = document.getElementById("filter-summary");
const styleChips = document.getElementById("filter-style");
const typeChips = document.getElementById("filter-type");
const sizeSelect = document.getElementById("filter-size");
const brandSelect = document.getElementById("filter-brand");
const cityLabel = document.getElementById("city-label");

const STYLES = [
  ["", "All"],
  ["eastern", "Eastern"],
  ["western", "Western"],
];
const TYPES = [
  ["", "All"],
  ["ready_to_wear", "Stitched"],
  ["unstitched", "Unstitched"],
];
const SIZES = ["XS", "S", "M", "L", "XL"];

const store = createStore(
  { style: "", type: "", size: "", brand: "", products: [], loading: true },
  render,
);

// --------------------------------------------------------------------------
// Rendering — pure string building, one write per mount point
// --------------------------------------------------------------------------

function chipGroup(options, selected) {
  return options
    .map(
      ([value, label]) =>
        `<button class="chip-btn" type="button" data-value="${value}" ` +
        `aria-pressed="${value === selected}">${esc(label)}</button>`,
    )
    .join("");
}

function availabilityLine(product, size) {
  if (product.sold_out) return `<span class="card__avail is-failed">Sold out</span>`;
  if (product.product_type === "unstitched") {
    return `<span class="card__avail is-ok">Free Size — stitched to measure</span>`;
  }
  if (size) return `<span class="card__avail is-ok">In stock in ${esc(size)}</span>`;
  return `<span class="card__avail is-unresolved">${product.available_sizes.length} sizes available</span>`;
}

function priceLine(product) {
  // An expired discount reports discount_pct = 0 from the API, so no
  // strikethrough can be rendered for a price that is no longer real.
  if (product.discount_pct > 0) {
    return `${pkr(product.discounted_price_pkr)}<span class="card__was">${pkr(product.price_pkr)}</span>`;
  }
  return pkr(product.price_pkr);
}

function productCard(product, size) {
  return `
    <a class="card ${product.sold_out ? "card--sold" : ""}" href="/product.html?id=${encodeURIComponent(product.id)}">
      ${productTile(product, "card__tile")}
      <p class="card__brand">${esc(product.brand)}</p>
      <p class="card__title">${esc(product.title)}</p>
      <p class="card__price">${priceLine(product)}</p>
      ${availabilityLine(product, size)}
    </a>`;
}

function render(state) {
  styleChips.innerHTML = chipGroup(STYLES, state.style);
  typeChips.innerHTML = chipGroup(TYPES, state.type);

  if (state.loading) {
    summary.textContent = "Loading…";
    return;
  }

  grid.innerHTML = state.products.map((p) => productCard(p, state.size)).join("");

  const n = state.products.length;
  summary.innerHTML =
    n === 0
      ? ""
      : `${n} ${n === 1 ? "piece" : "pieces"}${state.size ? ` available in ${esc(state.size)}` : ""}` +
        (hasFilters(state) ? ` · <button class="link-btn" id="clear">Clear filters</button>` : "");

  // Edge case #17: filters can legitimately combine to nothing — "western" plus
  // "unstitched" is a genuine contradiction, since unstitched is always eastern.
  // Say so and offer the one-click way out rather than leaving a blank page.
  empty.hidden = n !== 0;
  if (n === 0) {
    empty.innerHTML =
      `Nothing matches these filters${state.size ? ` in size ${esc(state.size)}` : ""}. ` +
      `<button class="link-btn" id="clear-empty">Clear filters</button>`;
  }
}

const hasFilters = (s) => Boolean(s.style || s.type || s.size || s.brand);

// --------------------------------------------------------------------------
// Data
// --------------------------------------------------------------------------

async function refresh() {
  const { style, type, size, brand } = store.get();
  store.set({ loading: true });
  try {
    const products = await fetchProducts({ style, type, size, brand });
    store.set({ products, loading: false });
  } catch (error) {
    store.set({ products: [], loading: false });
    summary.textContent = error.message;
  }
}

// --------------------------------------------------------------------------
// Handlers — mutate state, never the DOM
// --------------------------------------------------------------------------

function onChipClick(group, key) {
  return (event) => {
    const button = event.target.closest("button[data-value]");
    if (!button) return;
    store.set({ [key]: button.dataset.value });
    refresh();
  };
}

document.addEventListener("click", (event) => {
  if (event.target.id === "clear" || event.target.id === "clear-empty") {
    store.set({ style: "", type: "", size: "", brand: "" });
    sizeSelect.value = "";
    brandSelect.value = "";
    savePreferences({ size: null });
    refresh();
  }
});

async function init() {
  const prefs = loadPreferences();

  cityLabel.textContent = prefs.city ? `Delivering to ${prefs.city}` : "No city set";
  document.getElementById("change-city").addEventListener("click", () => {
    clearCity();
    window.location.href = "/";
  });

  sizeSelect.innerHTML =
    `<option value="">Any size</option>` +
    SIZES.map((s) => `<option value="${s}">${s}</option>`).join("");

  // A size chosen on the browse page persists to the product page, so the
  // customer never answers the same question twice.
  if (prefs.size) {
    sizeSelect.value = prefs.size;
    store.set({ size: prefs.size });
  }

  try {
    const brands = await fetchBrands();
    brandSelect.innerHTML =
      `<option value="">All brands</option>` +
      brands
        .map((b) => `<option value="${esc(b.name)}">${esc(b.name)} (${b.product_count})</option>`)
        .join("");
  } catch {
    brandSelect.innerHTML = `<option value="">All brands</option>`;
  }

  styleChips.addEventListener("click", onChipClick(styleChips, "style"));
  typeChips.addEventListener("click", onChipClick(typeChips, "type"));

  sizeSelect.addEventListener("change", () => {
    store.set({ size: sizeSelect.value });
    savePreferences({ size: sizeSelect.value || null });
    refresh();
  });

  brandSelect.addEventListener("change", () => {
    store.set({ brand: brandSelect.value });
    refresh();
  });

  await refresh();
}

init();
