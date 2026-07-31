/**
 * Landing page controller — the location gate.
 *
 * Single job: capture the delivery city once, then get out of the way.
 *
 * Asking beats guessing (PLAN.md decision #7). It is more honest than geo-IP,
 * and it moves confidence upstream: once the city is known, even the browse
 * cards can carry real delivery information.
 */

import { fetchDestinations } from "./api.js";
import { loadPreferences, savePreferences } from "./store.js";

const select = document.getElementById("city");
const continueBtn = document.getElementById("continue");
const skipBtn = document.getElementById("skip");
const warning = document.getElementById("gate-warning");

let destinations = [];

function go() {
  window.location.href = "/browse.html";
}

/**
 * Tell someone their city is unserviceable **here**, at the gate — not on every
 * product page afterwards (edge case #15). They can still browse; they simply
 * know where they stand before investing time.
 */
function showServiceabilityWarning(name) {
  const destination = destinations.find((d) => d.name === name);
  const unserviceable = destination && !destination.serviceable;

  warning.hidden = !unserviceable;
  if (unserviceable) {
    warning.textContent =
      `We don't deliver to ${name} yet. You're welcome to browse — ` +
      `prices are correct, but we can't promise a delivery date.`;
  }
}

async function init() {
  // A returning customer has already answered this question.
  if (loadPreferences().city) return go();

  try {
    destinations = await fetchDestinations();
  } catch {
    // If the API is unreachable the gate must not trap anyone on a dead page.
    return go();
  }

  select.insertAdjacentHTML(
    "beforeend",
    destinations
      .map((d) => `<option value="${d.name}">${d.name}${d.serviceable ? "" : " — not served yet"}</option>`)
      .join(""),
  );

  select.addEventListener("change", () => {
    continueBtn.disabled = !select.value;
    showServiceabilityWarning(select.value);
  });

  continueBtn.addEventListener("click", () => {
    if (!select.value) return;
    savePreferences({ city: select.value });
    go();
  });

  // Skipping is explicitly supported: the unresolved experience is fully built,
  // so a forced gate would cost conversions for nothing.
  skipBtn.addEventListener("click", () => {
    savePreferences({ city: null, skippedGate: true });
    go();
  });
}

init();
