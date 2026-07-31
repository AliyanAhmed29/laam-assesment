/**
 * Theme toggle.
 *
 * Single job: flip between light and dark, and remember the choice.
 *
 * Three states, not two: **auto** (follow the OS), **light**, **dark**. Storing
 * an explicit choice only when the user makes one means someone who never
 * touches the button still tracks their system setting — including when it
 * changes at sunset.
 *
 * The initial `data-theme` is set by a tiny inline script in each page's
 * `<head>`, before first paint. Doing it here instead would flash the light
 * theme first, because module scripts are deferred.
 */

const STORAGE_KEY = "laam.theme";
const media = window.matchMedia("(prefers-color-scheme: dark)");

function stored() {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

/** What the user is actually looking at right now. */
function effective() {
  return stored() || (media.matches ? "dark" : "light");
}

function apply(theme, button) {
  document.documentElement.dataset.theme = theme;
  if (!button) return;
  const dark = theme === "dark";
  button.textContent = dark ? "☀" : "☾";
  button.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
  button.setAttribute("title", button.getAttribute("aria-label"));
}

export function initTheme() {
  const button = document.getElementById("theme-toggle");
  apply(effective(), button);

  // No explicit choice yet? Keep following the OS as it changes.
  media.addEventListener("change", () => {
    if (!stored()) apply(effective(), button);
  });

  button?.addEventListener("click", () => {
    const next = effective() === "dark" ? "light" : "dark";
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* Storage unavailable — the toggle still works for this page view. */
    }
    apply(next, button);
  });
}

initTheme();
