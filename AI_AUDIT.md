# AI Audit Trail

Required deliverable per the assessment brief: *"When you start using AI, ask it
to build an audit trail of all activities."*

This file is **append-only** and written as work happens, not reconstructed
afterwards. Each entry records what was asked, what the AI produced, and what was
reviewed, corrected or rejected by me.

**Tool used:** Claude Code (Claude Opus 5), via the Claude Code CLI.

Entries are numbered in sequence. Timestamps are recorded at date granularity —
I have not invented clock times I did not record.

---

## Phase 1 — Understanding the brief

### Entry 1 · 2026-07-31 · Read the assessment
**Asked:** Read `Software Engineer Assessment .pdf` and extract its content.
**AI produced:** Full text extraction of the 4-page brief.
**My review:** Verified against the PDF directly. Noted two requirements that are
easy to miss because they sit inside the AI Usage section rather than Deliverables:
the audit trail must be started *when AI use begins*, and the README needs a
concrete example of correcting or rejecting AI output. Both are now planned for
rather than retrofitted.

### Entry 2 · 2026-07-31 · Domain research
**Asked:** Research LAAM as a company to ground the design in the real product.
**AI produced:** Web research — LAAM is a South Asian fashion marketplace, 1,000+
brands, 100k+ articles, ships to 100+ countries, top markets US / Canada / Middle
East / Pakistan, founded 2021, Lahore-based.
**My review:** Used this to justify specific design choices rather than as
decoration — notably cross-border delivery mattering, and unstitched vs.
ready-to-wear being a real category distinction in this market that affects
lead times.

---

## Phase 2 — Design, and where I pushed back

### Entry 3 · 2026-07-31 · First design proposal
**Asked:** Given the brief, what should be built?
**AI produced:** A "confidence-first product page" — per-size availability, price
breakdown, delivery estimate, alternatives rail, and a confidence summary panel.
**My review:** Directionally right, but two things were unspecified, which I
challenged (Entry 4).

### Entry 4 · 2026-07-31 · **Correction — cold start was unhandled**
**I raised:** The proposal assumed the user's size and delivery area were already
known. In reality a user lands on a product page having supplied neither, and
delivery charges depend on area — so what does the page actually show on arrival?
**AI response:** Conceded the gap and produced the three-tier resolution model
(unresolved → estimated → confirmed-for-you), with the rule *never render a
precise-looking value that is really a guess*, plus: guess location but never
guess size.
**Outcome:** This became the central thesis of the whole design. **The strongest
idea in the build came from correcting an AI omission, not from the AI's first
answer.**

### Entry 5 · 2026-07-31 · **Correction — "alternatives mode" was hand-waving**
**I raised:** The claim that an out-of-stock size "flips the page into
alternatives mode" was not a mechanism, just a phrase. How does it actually work?
**AI response:** Dropped the phrase — as literally described it implied a jarring
full-page transformation. Replaced with a precise mechanic: sold-out sizes stay
*tappable* rather than disabled (disabling is a dead end), and a failed check
changes exactly three things — the verdict row, the CTA, and a rail hard-filtered
by the constraint that failed. Generalised into a failure→recovery table.
**Outcome:** Turned a vague UI flourish into a testable architectural rule.

### Entry 6 · 2026-07-31 · Adversarial self-review
**Asked:** Self-evaluate the design critically before building anything.
**AI produced:** Nine ranked weaknesses in its own proposal. The material ones:
the scope was a 7–9 hour build being submitted against a 3–4 hour brief; the
delivery estimator would be hollow theatre unless it contained genuine calendar
logic; discovery was under-served relative to the assessment's own title; and the
summary panel risked being redundant UI restating facts already on screen.
**My review:** Accepted the critique and required a cut list. Scope reduced to fit
the stated time limit. The summary panel was given an explicit kill condition
rather than being assumed worth building.

---

## Phase 3 — Technical decisions

### Entry 7 · 2026-07-31 · **Rejection — Next.js recommendation overruled**
**AI initially recommended:** Next.js full-stack.
**I rejected it:** My preference was plain HTML/CSS/JS with a FastAPI backend, and
I asked for an actual evaluation rather than a default.
**What the AI found on re-examination:** LAAM's own backend engineering job posting
specifies Python (Django/Flask/FastAPI) with PostgreSQL. Independently, Next.js
API routes make backend design *less* visible — no schema validation by default,
no generated docs — while the brief grades backend and frontend design separately.
**AI conceded:** the original suggestion was a reflex "modern full-stack" default,
not a decision reasoned from this brief.
**Outcome:** FastAPI + Pydantic + SQLite, vanilla frontend served by FastAPI.
**This is the primary example for README §9.**

### Entry 8 · 2026-07-31 · Vanilla-JS risk mitigation
**Asked:** What is the risk of no frontend framework, given "maintainability" is
graded?
**AI produced:** The honest failure mode — `getElementById(...).textContent = ...`
scattered across handlers. Mitigation: one `state` object, one `render(state)`,
handlers that only mutate state and call render.
**My review:** Accepted, and required it be enforced structurally — components as
pure `state → HTML string` functions, a single module owning the DOM, a single
module owning `fetch`.

### Entry 9 · 2026-07-31 · **Improvement — merged two endpoints into one**
**Context:** The draft had separate `/price` and `/delivery-estimate` endpoints.
**My reasoning:** Setting the destination resolves *both* the delivery date and
the final total, so two endpoints meant two round trips for a single user action.
**Outcome:** Merged into one `/confidence` endpoint. Logged as decision #5 in
`PLAN.md`.

---

## Phase 4 — Planning and implementation

### Entry 10 · 2026-07-31 · Build plan written
**Asked:** Produce a detailed plan document capturing every decision so far.
**AI produced:** `PLAN.md` — 19 sections covering thesis, scope, user flow,
failure→recovery, stack rationale, folder structure and layer rules, data model,
API contracts, domain pseudocode, a 13-row edge case register, seed requirements,
test priorities, frontend state shape, time budget, known risks and a decision log.
**My review:** Kept as the source of truth. Changes go here first, then into code.

### Entry 11 · 2026-07-31 · Scaffold
**Asked:** Scaffold the project structure from `PLAN.md` §7.
**AI produced:** Directory tree, `requirements.txt`, `.gitignore`, and stub modules
carrying their single-responsibility docstrings, Pydantic schemas, and typed
function signatures for the domain layer.
**My review:** Verified the layer rules hold — `domain/` imports neither FastAPI
nor `sqlite3`, so the priority test suites need no fixtures or test client.

### Entry 12 · 2026-07-31 · **Correction — AI's own dependency claim was wrong on Windows**
**AI asserted:** "Python 3.13 — `zoneinfo` is stdlib, so the calendar logic needs
no extra dependency."
**What actually happened:** the scaffold verification failed with
`ZoneInfoNotFoundError: 'No time zone found with key Asia/Karachi'`. Windows ships
no system tz database, so stdlib `zoneinfo` cannot resolve IANA keys without the
`tzdata` package.
**Fix:** added `tzdata>=2024.1` to `requirements.txt` with a comment explaining
why it is needed on Windows and harmless elsewhere.
**Why this is worth logging:** the claim was stated confidently and was wrong on
the target platform. It was caught because the scaffold was *executed* rather
than eyeballed — the whole reason for verifying imports before writing any real
logic. A reviewer on Windows would otherwise have hit this on first run.

### Entry 13 · 2026-07-31 · Scaffold verified
**Ran:** venv creation, dependency install, an import check across all backend
modules, OpenAPI schema generation, and `pytest`.
**Result:** all modules import cleanly; all 6 endpoints appear in the generated
schema with 23 Pydantic models; 46 tests collect and skip pending implementation.
**One false alarm investigated:** `app.routes` appeared to be missing the API
routes. Cause was FastAPI 0.141 representing an included router as a single
`_IncludedRouter` entry instead of flattening its routes — not a wiring bug.
Confirmed correct by generating the OpenAPI schema rather than trusting the
route list.

---

## Phase 5 — Flow revision and full implementation

### Entry 14 · 2026-08-01 · **Direction change — I redesigned the flow**
**I specified:** a location-first landing page; brand filters on the listing;
a left-hand card on the product page carrying delivery dates (with the city
editable there), a full price breakdown including tax, and a "view alternatives"
button. I also asked the AI to define what "similar" should mean, and specified
a minimal white design.
**AI contribution:** agreed the flow was an improvement on its own (it replaced
its geo-IP guess with simply asking, which is more honest); split my
"eastern/western/stitched/unstitched" into two independent filter axes; and
proposed the similarity model, adding **fabric** as a ranking signal on the
grounds that fabric encodes season and occasion in this market.
**My review:** accepted. Fabric-as-occasion is the single most domain-specific
idea in the ranking and I would not have specified it myself.

### Entry 15 · 2026-08-01 · **Correction — AI flagged a tax error I was about to introduce**
**I asked for:** "the final price with delivery charges tax and everything".
**AI pushed back:** Pakistani retail prices are GST-inclusive. Adding 18% on top
of the listed price would misrepresent how PK stores price *and* would make the
"no surprises" promise itself the source of a surprise.
**Outcome:** GST is disclosed as a component (`subtotal × 18/118`), never added.
Exports are zero-rated, so international orders show a duties note instead.
**Worth noting:** this is the one case where the AI corrected *me* rather than
the other way round, and it was right.

### Entry 16 · 2026-08-01 · Additions, and a tension with the thesis
**I specified:** the city must be selectable on the product page; before it is
known, show delivery charges as an approximate range and still show a final
price marked as pending.
**Tension the AI raised:** this appears to violate the project's own rule
("never render a precise-looking value that is really a guess").
**Resolution:** the rule was sharpened rather than abandoned — uncertainty must
live *in the shape of the value* (a range), not only in a caption. It also
declined to range the delivery *date*, on the grounds that "3–20 days" spanning
Lahore-to-Canada is noise, and showed dispatch time instead.
**My review:** accepted both.

### Entry 17 · 2026-08-01 · Implementation
**Produced:** domain layer (delivery, pricing, alternatives, confidence),
repository, 7 API endpoints, 35-product generated seed, three frontend pages
with the state→render loop, and 91 tests.
**My review:** I drove the running app through every edge case in the register
rather than trusting the test suite alone.

### Entry 18 · 2026-08-01 · **Four bugs found by running the code, not reading it**
1. **`%-d` strftime** — POSIX-only; would crash the backend on Windows. Caught
   before it shipped, replaced with a portable helper.
2. **`Size.S` in customer copy** — Python 3.11 changed `__format__` for
   str-mixin enums, so f-strings rendered `Size.S` instead of `S`. Fixed by
   unwrapping enums at the API boundary.
3. **Two red rows for one problem** — a sold-out size also failed the delivery
   check, which was merely its consequence. It also polluted `failed_checks`,
   which would have wrongly hard-filtered the alternatives rail. Reclassified as
   unresolved; regression test added.
4. **Contradictory panels** — the price card quoted "Delivery: Free · Total
   Rs 145,000" for a destination the delivery panel had just said we cannot ship
   to. Added a `deliverable` flag so there is simply no total for an address we
   cannot reach; two regression tests added.

Bugs 3 and 4 were **design** errors, not typos: the AI's output was internally
consistent and passed its own tests, but produced a UI that contradicted itself.
Only exercising the real interface surfaced them.

### Entry 19 · 2026-08-01 · **Rejection — a false claim in the seed data**
**AI had written** a comment asserting one product was "deliberately isolated,
so nothing passes the hard filter and the rail shows its empty state". Once the
generated filler was added this was **no longer true** — six alternatives
existed.
**My review:** rather than leave a comment that lied about the data, I had it
corrected to describe reality and to point at the case that *does* exercise the
empty rail (an unreachable `arrive_by` deadline). A stale comment is worse than
no comment.

### Entry 20 · 2026-08-01 · README and final verification
**Ran:** full suite (91 passing), plus a manual pass through the landing gate,
browse filters, cold start, sold-out recovery, expired discount, unstitched
stitching lead, unserviceable city, international-shipping refusal, unreachable
deadline, and the zero-results filter state.

---

## Phase 6 — Product imagery

### Entry 21 · 2026-08-01 · **Declined — scraping LAAM's own product photos**
**I asked for:** images downloaded from the official LAAM site "if it allows,
and if not then from anywhere feasible".
**Checked first:** `laam.com/robots.txt` — it disallows `/admin`, `/cart`,
`/checkout`, `/search`, `/assets/` and similar, but permits product pages. That
is beside the point: robots.txt governs crawling, not copyright. The photographs
are LAAM's and their brands' intellectual property, and nothing licenses
redistribution in a third-party project.
**Second, product-level reason:** every brand in this seed is *invented*
specifically so no real company has fabricated stock, pricing or delivery data
attributed to it (README §4). Attaching real photographs of real garments to
invented brands would have undone the exact protection that decision bought.
**Alternative taken:** Openverse (the Creative Commons index), filtered to
CC0 / CC-BY / CC-BY-SA and excluding non-commercial and no-derivatives licences.
29 images, fully attributed in `frontend/img/products/ATTRIBUTION.md`.

### Entry 22 · 2026-08-01 · Image pipeline built
**Produced:** `seed/fetch_images.py`; `images.json` manifest; per-category
round-robin assignment in `generate.py`; a shared `productTile()` frontend
helper; and CSS for photo tiles.
**Design point I insisted on:** the text tile remains a live fallback rather
than being deleted. A reviewer who never runs the fetcher, or who deletes an
image file, still gets a working catalogue — `onerror` removes a broken `<img>`
and the caption underneath shows through. The image step is optional by design.

### Entry 23 · 2026-08-01 · **Four bugs in the fetcher, all found by running it**
1. **Windows console encoding** — `✓` and `→` in progress output crashed the
   script under cp1252. Replaced with ASCII.
2. **Wikimedia thumbnail widths** — arbitrary widths return HTTP 400; only a
   fixed set of sizes is served. Fixed at 640px with a fallback to the original.
3. **Duplicate filenames** — distinct records slugified to the same name, so the
   second silently reused the first one's file and the manifest listed the same
   image twice. Added a uniqueness counter.
4. **Near-identical results** — the first successful run pulled *nine* variants
   of one linen dress and five of one fabric shot, because photographers upload
   numbered series. Added a `series_key()` that collapses trailing digits, plus
   a per-search-term cap.

Also capped downloads at 1.2 MB after the first run produced a 6.2 MB image and
a 25 MB total. Final: 29 images, 7.0 MB, largest 804 KB.

### Entry 24 · 2026-08-01 · Verification, and a false alarm I did not trust
Browser instrumentation initially reported **all 35 images broken**
(`naturalWidth === 0`). Rather than "fixing" that, I checked the actual HTTP
responses: 200, `image/jpeg`, decoding at 683×1024. The cause was
`loading="lazy"` in a browser pane that was not compositing frames, so
`IntersectionObserver` never fired — a measurement artifact, not a defect.
Confirmed properly by forcing eager loading (35/35) and by a server-side check
that every `image_url` in the seed resolves to a file on disk.

**Worth recording:** the instinct to "fix" a red signal without diagnosing it
would have introduced a real regression (removing lazy loading) to chase a
phantom.

---

## Phase 7 — Dark mode, card sizing, deadline feedback

### Entry 25 · 2026-08-01 · Dark mode
**I specified:** dark mode across the whole site.
**Produced:** light/dark tokens driven by both `prefers-color-scheme` and an
explicit `data-theme`, a header toggle, and `theme.js`.
**Two things I required beyond the obvious:** a **three-state** model (auto /
light / dark) so a customer who never touches the toggle keeps following their
OS; and a pre-paint inline script in each `<head>`, because a deferred module
would flash the light theme first.
**A real bug this exposed:** product tiles were emitting a full `hsl(...)`
string as an inline style. Inline styles cannot respond to a media query or a
theme switch, so every tile would have stayed washed-out in dark mode. Changed
so only the **hue** is inline and CSS themes saturation and lightness.

### Entry 26 · 2026-08-01 · Card sizing, measured rather than guessed
**I reported:** the product-page card was too big.
**Approach:** measured before changing anything — 952px tall, with Delivery at
337px and Price at 307px. Reductions: collapsed the delivery step breakdown
behind a "Why this date?" `<details>`, demoted the secondary action from a full
button to a text link, tightened spacing and type, and shortened the deadline
label after measurement showed it was wrapping both control rows onto two lines.
**Result:** 952px -> **687px** (-28%), verified by measurement rather than by eye.

### Entry 27 · 2026-08-01 · **Root cause found for the misplaced deadline message**
**I reported:** the "can't arrive in time" message appears at the bottom of the
page instead of near the date input.
**Diagnosis — the cause was not layout.** `deliveryPanel` derived its own
severity from `delivery.available`. On a missed deadline the estimate *does*
exist; it simply lands too late — so the panel rendered a **green tick with the
arrival window**, and the server's failure message ("Arrives 13 Aug – 20 Aug —
after 10 Aug") was never displayed anywhere. The only signal was the alternatives
heading at the foot of the page.
**Fix:** severity now comes from the server's `delivery` check, which already
computed the correct copy. The verdict renders in a bordered box **8px below the
date input**, with an inline "See what arrives in time" action.
**Why this matters:** the same class of bug — a component re-deriving state the
server already decided — was fixed once before in entry 18. Worth watching for.

<!-- Append new entries below this line as work proceeds. -->

