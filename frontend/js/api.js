/**
 * HTTP client.
 *
 * Single job: **the only module in the frontend that calls `fetch`.**
 *
 * Same origin as the API (FastAPI serves these files), so no base URL and no
 * CORS. Every function returns parsed data or throws — callers put the error
 * into state and let `render()` deal with it.
 */

const BASE = "/api";

/** Builds the query string, checks status, parses JSON. Null/undefined params
 *  are dropped so callers can pass a whole state slice without filtering. */
async function get(path, params = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== "") query.set(key, value);
  }
  const qs = query.toString();
  const response = await fetch(`${BASE}${path}${qs ? `?${qs}` : ""}`);

  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || `Request failed (${response.status})`);
  }
  return response.json();
}

export const fetchDestinations = () => get("/destinations");
export const fetchBrands = () => get("/brands");

export const fetchProducts = (filters = {}) => get("/products", filters);
export const fetchProduct = (id) => get(`/products/${encodeURIComponent(id)}`);

/**
 * Price + delivery + verdict in one round trip.
 *
 * Every argument is optional on purpose. Calling this with nothing but a
 * product id is the cold-start case and must succeed — it returns `unresolved`
 * checks and ranged prices rather than an error.
 */
export const fetchConfidence = (id, opts = {}) =>
  get(`/products/${encodeURIComponent(id)}/confidence`, {
    size: opts.size,
    destination: opts.destination,
    arrive_by: opts.arriveBy,
    stitching: opts.stitching,
  });

export const fetchAlternatives = (id, opts = {}) =>
  get(`/products/${encodeURIComponent(id)}/alternatives`, {
    size: opts.size,
    destination: opts.destination,
    arrive_by: opts.arriveBy,
  });

export async function createRestockAlert(id, { size, email } = {}) {
  const response = await fetch(`${BASE}/products/${encodeURIComponent(id)}/restock-alert`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ size, email: email || null }),
  });
  if (!response.ok) throw new Error("Could not create the alert");
  return response.json();
}
