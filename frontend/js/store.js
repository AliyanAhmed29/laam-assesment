/**
 * State container and preference persistence.
 *
 * Single job: hold state, notify one subscriber when it changes, and remember
 * the customer's city and size between visits.
 *
 * This is the mitigation for the one real risk of skipping a framework
 * (PLAN.md §6). Vanilla JS on a stateful page usually decays into
 * `getElementById(...).textContent = ...` scattered across a dozen handlers,
 * with the UI silently drifting out of sync with reality.
 *
 * The discipline that prevents it, in three rules:
 *
 *   1. All state lives in one object.
 *   2. Handlers only ever `set()` — they never touch the DOM.
 *   3. One `render(state)` redraws from state. It is the only DOM writer.
 *
 * That is unidirectional data flow in about forty lines. Choosing it
 * deliberately over React is a stronger signal than importing React would be.
 */

const STORAGE_KEY = "laam.preferences";

/** Create a store. `onChange` is the single render function. */
export function createStore(initial, onChange) {
  let state = { ...initial };

  return {
    get: () => state,
    set(patch) {
      state = { ...state, ...patch };
      onChange(state);
      return state;
    },
  };
}

/**
 * Restore city and size.
 *
 * Returning customers should never re-enter what they already told us. Values
 * restored this way are marked `source: "stored"` rather than `"user"` — we
 * remember the preference without pretending it was confirmed for this visit.
 *
 * Wrapped in try/catch because localStorage throws in private-browsing modes on
 * some browsers, and a storage failure must never take the page down with it.
 */
export function loadPreferences() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
  } catch {
    return {};
  }
}

/** Persist city and size. Never persists a computed price or date — those are
 *  the server's to decide, every time. */
export function savePreferences(patch) {
  try {
    const merged = { ...loadPreferences(), ...patch };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(merged));
  } catch {
    /* Storage unavailable — the session still works, it just won't be remembered. */
  }
}

export function clearCity() {
  savePreferences({ city: null });
}
