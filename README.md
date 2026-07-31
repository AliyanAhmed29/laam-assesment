# LAAM — Product Discovery & Purchase Confidence

A small full-stack slice that helps a shopper decide, with confidence, whether a
South Asian fashion product is right for **them** — their size, their city,
their deadline, their final price.

FastAPI + SQLite backend · plain HTML/CSS/ES-modules frontend · no build step.

```bash
cd backend && python -m uvicorn app.main:app --reload --port 8000
```

Then open **http://127.0.0.1:8000** — full setup in [§5](#5-how-to-run).

---

## Demo

A short walkthrough of the flow — location gate, browse filters, the confidence
card, and the sold-out and missed-deadline recovery paths:

**▶ [Watch the demo](PASTE_YOUR_DRIVE_LINK_HERE)**

> _Paste the shared Google Drive link above (set to "Anyone with the link can
> view")._

---

## 1. Problem Understanding

The brief describes a shopper who likes a product but isn't confident about
size, delivery, final price, or whether something better exists.

I read that as one underlying pain point:

> **A shopper's confidence collapses at the moment they try to turn a general
> interest in a product into a specific decision for themselves.**

A standard product page answers questions about *the product*. It does not
answer questions about *this product, for me*. That gap is where the drop-off
happens — so the slice I built turns a product page from a **description** into
an **answer**.

### The thesis everything hangs on

> Confidence does not come from showing more numbers. It comes from being
> visibly honest about which numbers are actually yours.

A confident "Delivery in 3 days" that turns out wrong for your city destroys
more trust than an empty row ever would. So the build follows one rule:

> **Never render a precise-looking value that is really a guess. Where a value
> is genuinely uncertain, express that uncertainty in the shape of the value
> itself — a range — not just in a caption beneath it.**

`Rs 199` before we know your city is a lie. `Free – Rs 4,200` is honest, because
a range announces itself as a range. This is what lets the price card stay
*useful* at cold start instead of sitting blank.

Two mechanisms follow from the thesis, and they are the two original ideas here:

**(a) Resolution states.** Every claim on screen is *unresolved*, *estimated*, or
*confirmed for you*, and each is styled differently. The page opens mostly
unresolved and sharpens as the shopper supplies inputs.

**(b) Failure → recovery coupling.** Every check that can pass can also fail, and
each *specific* failure produces a *specific* recovery. A sold-out size and a
too-late delivery date are different problems and must never produce the same
generic "you may also like".

---

## 2. Scope

### Built

| Area | What it does |
|---|---|
| **Landing** | Asks for the delivery city once (skippable), remembers it |
| **Browse** | Four filters — style, type, size, brand — with availability on the card |
| **Product page** | Per-size stock, confidence card, price breakdown, delivery window |
| **Alternatives** | One rail, two triggers: a button, or an automatic constraint-filtered open when a check fails |
| **Restock alerts** | Captures demand for a sold-out size instead of losing the shopper |
| **Tests** | 91 tests; delivery and pricing covered in depth |

### Deliberately not built

| Cut | Why |
|---|---|
| Checkout, cart, payments, auth | Brief explicitly excludes them |
| Search | Four filters cover discovery; search is a different problem |
| Multi-currency | Rs throughout — FX is a rabbit hole with no bearing on the thesis |
| Real geo-IP | We *ask* instead. Asked beats guessed, and it costs nothing |
| Budget / country-specific failure modes | The architecture generalises — 2 of 4 recovery paths implemented, see [§7](#7-tradeoffs) |

Full design record, including the decision log and edge-case register, is in
[`PLAN.md`](PLAN.md).

---

## 3. User Flow

**1 · Landing.** One question — *"Where should we deliver?"* — with a line saying
why we ask: *"so every price and delivery date you see is real."* Nine
destinations, a Continue button, and a quiet **Skip for now**.

The city persists to `localStorage`, so returning visitors go straight to browse
and never see this screen again. Picking an unserviceable city (Gwadar is seeded
as one) tells you **right there**, rather than letting you discover it on every
product page afterwards.

**2 · Browse.** Style (Eastern/Western) and Type (Stitched/Unstitched) are
presented as two independent axes rather than one crowded list — unstitched is
always eastern, so the combinations stay sensible. Plus size and brand. Cards
carry an availability line, so *"is it in my size?"* is answered **before** the
click rather than after it.

**3 · Product page.** Image, price, and size chips on the left; the
**confidence card** beside them, ordered the way a person actually decides:

1. **Your size** — reflects the chip selection, or prompts for one
2. **Arrives** — date window, with the city editable inline
3. **You'll pay** — full breakdown, GST disclosed, delivery included
4. **Action** — Add to cart / Notify me / Select a size
5. **View alternatives** — always available

**4 · Recovery.** Sold-out sizes stay **tappable**. Disabling them is the
industry default and it's a dead end — the shopper learns nothing and leaves.
Tapping a struck-through chip means *"M is the size I want"*, which is intent
worth answering. Three things then change (the images and description do not
move): the size row turns red, the CTA becomes *Notify me when it's back*, and
the alternatives rail opens **hard-filtered to items actually in stock in M**.

### Cold start — the state every first-time visitor is in

If someone skips the gate, the card must still be useful:

| Row | Behaviour |
|---|---|
| **Subtotal** | **Exact.** Price and discount are knowable now, so they anchor the card |
| **Delivery fee** | A **range** across serviceable destinations — *"Free within Pakistan · Rs 1,900–4,200 international"* |
| **Total** | A **range**, styled as estimated, with the prompt to resolve it |
| **Arrives** | *"Ships from Lahore in 2 working days"* + *"Select your city for arrival dates"* |

That last row matters. I deliberately do **not** show an arrival range before the
city is known: "3–20 days" spanning Lahore-to-Canada is noise. Dispatch time is
location-independent and completely certain, so it's shown instead.

Selecting the city resolves all three rows in **one request** — which is why
price and delivery share a single `/confidence` endpoint.

---

## 4. Technical Approach

### Stack, and why

**FastAPI + Pydantic + SQLite; vanilla frontend served by FastAPI** — one
process, one command, no CORS.

I initially reached for Next.js and reversed that decision. LAAM's own backend
engineering posting asks for **Python (Django/Flask/FastAPI)** with PostgreSQL.
Independently of stack-matching, FastAPI is simply better for an assessment that
grades backend and frontend design *separately*: Pydantic models **are** the data
model, and `/docs` hands the reviewer an interactive API explorer for free.
Next.js API routes would have made backend design less visible, not more.

**No frontend framework.** The PDP carries six pieces of state, which is well
inside what vanilla JS handles — *provided* there's a discipline. The failure
mode is `getElementById(...).textContent = ...` scattered across a dozen
handlers. The mitigation is structural:

> One `state` object · one `render(state)` · handlers only mutate state and call
> render. Components are pure `state → HTML string`.

That's unidirectional data flow in about forty lines. I'd switch to React the
moment this grew past two pages with shared component state.

### Architecture

```
backend/app/
├── main.py         app wiring, static mount, startup seed
├── api.py          the ONLY module that knows about HTTP
├── schemas.py      Pydantic contracts
├── db.py           schema + seed loading
├── repository.py   the ONLY module that writes SQL
└── domain/         pure logic — imports neither FastAPI nor sqlite3
    ├── delivery.py     the centrepiece
    ├── pricing.py      GST-inclusive, ranged when unresolved
    ├── alternatives.py what "similar" means
    └── confidence.py   verdict + CTA assembly
```

**The layer rule earns its keep in the tests.** Because `domain/` is pure and
`now` is injected rather than read from the clock, `test_delivery.py` needs no
fixtures, no test client, and no database. Fast tests are the tests that
actually get written inside a time limit.

The frontend mirrors it: `api.js` is the only module calling `fetch`, each page
controller is the only module touching the DOM, and `components/` are pure
functions with no state of their own.

### API

| Endpoint | Purpose |
|---|---|
| `GET /api/destinations` | Location picker, including unserviceable rows |
| `GET /api/brands` | Filter options with counts |
| `GET /api/products?style=&type=&size=&brand=` | Browse |
| `GET /api/products/{id}` | Detail with per-size stock **status** |
| `GET /api/products/{id}/confidence?size=&destination=&arrive_by=` | Price + delivery + verdict |
| `GET /api/products/{id}/alternatives?…` | Ranked recovery |
| `POST /api/products/{id}/restock-alert` | Capture demand |

**Every query parameter is optional.** `/confidence` must answer correctly
knowing *nothing* — returning unresolved checks and ranged prices, never a 422.
A naive implementation makes size and destination required and breaks the exact
state 100% of first-time visitors are in.

### Data model

`products` (35 rows, 8 brands, 4 categories) → `variants` (per-size stock),
plus `destinations` (9 zones with transit ranges, fees, thresholds and a
serviceability flag) and `restock_alerts`.

Stock reaches the client as a **status** — `in_stock` / `low_stock` /
`out_of_stock` — never a raw quantity. Inventory data is not customer data. The
exact count is revealed only when it's genuinely low ("Only 2 left").

The seed is a **design artifact, not filler**: every edge case in the register
has a product engineered to trigger it, documented inline in
[`seed/generate.py`](backend/seed/generate.py).

### Three decisions worth defending

**Delivery is real, not `today + random(3,7)`.** Order cutoff at 17:00
Asia/Karachi, brand dispatch lead, stitching lead for unstitched, zone transit,
and a working-day calendar skipping Sundays and public holidays. **14 August 2026
(Independence Day) falls inside the live estimate window**, so the calendar
visibly moves dates in the running demo rather than being an unverifiable claim.
Always a range; it refuses rather than fabricates, with five distinct reasons.

**GST is disclosed, never added.** Pakistani retail prices are tax-inclusive. If
I showed Rs 8,900 and added 18% at the end, I'd misrepresent how every PK store
prices — and manufacture the exact surprise this design promises to prevent. So
GST is reported as a component: `subtotal × 18/118`, not `× 0.18`. Exports are
zero-rated, so international destinations show no GST line and get a disclosed
duties note instead.

**"Similar" is defined, not vibes.** The real question is *"what else would do
the job this product was going to do?"* — and in South Asian fashion that job is
mostly **occasion**. There's no occasion tag, so three fields approximate it:

*Hard requirements (never violated):* same category · in stock in the requested
size · deliverable to the chosen city · must not fail the same check the base
product failed.

*Ranking:* passes the failed check (40) · price proximity (25) · **same fabric
(15)** · same type (10) · arrives sooner (10) · different brand (5).

Fabric is the domain-specific signal and the reason this beats a generic
recommender: fabric encodes season *and* occasion here — lawn is summer casual,
chiffon and jamawar are formal, khaddar is winter. Two same-priced pret suits in
lawn are far closer substitutes than lawn and velvet. **Colour is deliberately
excluded** — someone who liked teal is often happy with rose.

Every card states **why it's shown** ("In stock in M · Same fabric — lawn · Rs 800
less"), sourced from the server so a card can never claim something the ranking
didn't actually check.

### Theming

Light and dark, with a toggle in the header. **Three states, not two:** *auto*
(follow the OS), *light*, *dark*. An explicit choice is only stored when the
customer makes one, so someone who never touches the toggle keeps tracking their
system setting — including when it flips at sunset.

Two details worth noting. A tiny inline script in each `<head>` sets
`data-theme` **before first paint**; doing it in the deferred module would flash
the light theme first. And product tiles carry only a **hue** inline
(`--tile-h`), with saturation and lightness themed in CSS — an inline
`hsl(...)` string cannot respond to a theme switch, so the tints would have
stayed washed-out in dark mode.

### Assumptions

- Prices are GST-inclusive at 18%; exports zero-rated.
- Couriers work Saturdays, not Sundays; two public holidays seeded.
- Unstitched fabric is `Free Size`, stitched to measurement — so it satisfies
  **any** size filter rather than being hidden from one.
- Brand and product data is fabricated. Brand names are invented, not real
  companies, so no real business has fake stock or pricing attributed to it.

### On the product imagery

**LAAM's own catalogue photos are deliberately not used.** They are copyrighted
by LAAM and its brands, and nothing in [laam.com/robots.txt](https://laam.com/robots.txt)
grants a licence to copy and redistribute them. There is also a product reason:
since every brand here is invented specifically so no real company has
fabricated stock and pricing attached to it, pinning real photographs of real
garments onto those invented brands would undo exactly that protection.

Instead, [`seed/fetch_images.py`](backend/seed/fetch_images.py) pulls 29 openly
licensed photographs (CC0 / CC-BY / CC-BY-SA) via the
[Openverse](https://openverse.org) index, filtering out non-commercial and
no-derivatives licences. Full credit for every image is in
[`frontend/img/products/ATTRIBUTION.md`](frontend/img/products/ATTRIBUTION.md).

These are honest **stand-ins**: real photographs of South Asian clothing and
textiles, not photographs of these fictional products. Much of the openly
licensed pool is documentary rather than studio product photography, so the fit
is thematic rather than exact. Real catalogue shots drop in by replacing the
files and re-running `generate.py`.

The image step is **optional**. If the manifest is absent, every product falls
back to a tinted tile showing its short description, so the app is fully usable
without ever running the fetcher.

---

## 5. How to Run

**Requires Python 3.11+.** No Node, no build step.

```bash
python -m venv .venv
```

```bash
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

```bash
cd backend && ..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

On macOS/Linux use `.venv/bin/python` instead.

Then open:

| URL | |
|---|---|
| **http://127.0.0.1:8000** | The app — starts at the location gate |
| **http://127.0.0.1:8000/docs** | Interactive API documentation |

The SQLite database is **rebuilt from the JSON seed on every startup**, so the
demo is identical on every run. To regenerate the seed itself:

```bash
cd backend && ..\.venv\Scripts\python.exe seed\generate.py
```

Product images are committed, so nothing extra is needed. To re-download them
from scratch (requires network; takes a couple of minutes):

```bash
cd backend && ..\.venv\Scripts\python.exe seed\fetch_images.py
```

### Worth clicking

- **Teal Embroidered Lawn 3-Piece** → tap the struck-through **M** for the full
  sold-out recovery path.
- **Unstitched Emerald 3-Piece** → stitching lead time, and 14 Aug appearing in
  the skipped dates.
- **Formal Gharara — Gold** → discount expired 10 July, so it shows list price
  with *no* strikethrough.
- **Bridal Lehnga — Crimson** + set city to **United Kingdom** → the brand ships
  domestically only, so there's no total at all.
- Set city to **Canada** with a deadline of **10 Aug** → nothing in the catalogue
  can make it, and the rail says so instead of padding itself.

### Tests

```bash
cd backend && ..\.venv\Scripts\python.exe -m pytest -q
```

---

## 6. Tests

**91 tests, all passing**, in priority order:

| Suite | Count | Covers |
|---|---|---|
| `test_delivery.py` | 29 | Cutoff rollover, Sunday skipping, the 14 Aug holiday, stitching lead, range ordering, every refusal reason, deadline judgement |
| `test_pricing.py` | 21 | Threshold boundary (exactly at / one rupee under), expired discounts, GST-on-inclusive-price, export zero-rating, unresolved ranges, undeliverable destinations |
| `test_alternatives.py` | 16 | The hard filter never leaking a same-failure item; deterministic ordering; every result carrying a reason |
| `test_api.py` | 25 | The cold-start contract, failure paths, 404s, and that raw stock never leaks |

Delivery was tested first deliberately: it has the most branching, the highest
consequence if wrong, and it's the pillar the whole design rests on.

Two assertions I'd point a reviewer at:

- `test_arrives_in_time_judges_the_pessimistic_end_of_the_window` — the deadline
  is judged on `arrives_to`, never `arrives_from`. Telling someone they'll make
  their event based on the optimistic end of a range is exactly the
  confident-but-wrong claim this design exists to prevent.
- `test_brand_that_does_not_ship_abroad_quotes_no_total` — the price card and
  delivery panel can never contradict each other.

**Not covered:** no frontend tests. With the time available I chose depth on the
domain logic over breadth. If I added one more suite it would be Playwright over
the three failure→recovery paths, since those involve the most state
coordination and are where a regression would be least visible.

---

## 7. Tradeoffs

**Scope was cut, deliberately and early.** My first design was honestly a 7–9
hour build presented as a 3–4 hour one — which is itself a prioritisation
failure on an assessment that grades prioritisation. I ran an adversarial review
of my own plan before writing code and cut: multi-currency, geo-IP, dark mode,
and two of the four failure→recovery paths.

**Two of four recovery paths.** Size-sold-out and can't-arrive-in-time are
implemented; over-budget and country-not-served are not. The architecture
generalises — recovery is a table keyed on which check failed — but implementing
all four would have been repetition rather than new evidence.

**Depth over breadth in tests.** No frontend tests at all, in exchange for
thorough coverage of delivery and pricing. Those two modules are where a silent
bug costs a customer real money or a missed wedding.

**35 products, not 15.** I generated more than strictly needed because with a
dozen products the alternatives rail returns one result and the ranking
function's quality is invisible — untestable in practice and unreviewable.

**The location gate adds a step before value.** It's mitigated by skip and
persistence, but it *is* a real conversion cost and I'd want to A/B it rather
than assume it.

**The "need it by" field is the highest-variance idea here.** It either reads as
genuine insight into occasion-driven buying (weddings, Eid) or as invented
ceremony. I kept it because without it the delivery pillar has no consequence —
but it's optional, secondary, and never blocking.

---

## 8. Future Improvements

**Correctness and scale first.** Move to PostgreSQL — a one-class change, since
`repository.py` is the only module writing SQL. Delivery estimates should come
from real courier SLAs per lane rather than a static zone table, and `on_time_rate`
should be computed from actual delivery history per brand and lane, not seeded.

**Learn the ranking instead of hand-tuning it.** Today `alternatives.py` is a
hand-weighted linear scorer. The weights are reasoned, but they are my
priors — not evidence. The path I would take, in order:

1. **Content-based nearest neighbours first.** Encode each product as a feature
   vector — one-hot category and fabric, log-scaled price, brand tier, colour
   family, dispatch lane — and retrieve neighbours by cosine distance (KNN is
   the right starting point precisely because it needs no interaction history,
   so it works on day one and on brand-new SKUs).
2. **Then a learned re-ranker.** Once there is click and purchase data, replace
   the fixed weights with a learning-to-rank model (LambdaMART or an XGBoost
   ranker) trained on `(shown → clicked → added → purchased → kept)` tuples.
   Optimising for *kept* rather than *clicked* matters in fashion, where return
   rates are high and a click is a weak signal of satisfaction.
3. **Then collaborative signal.** "Shoppers who substituted away from X ended up
   buying Y" is the strongest substitution evidence there is, and it captures
   taste that no attribute vector encodes. It needs volume, so it comes last.

**The hard filters must stay hard.** Availability in the requested size,
deliverability to the chosen city, and the failed-check exclusion are business
constraints, not features for a model to trade off. A learned scorer that
outranks an out-of-stock item into the rail would break the exact promise this
page exists to make. The model re-ranks *within* the filtered candidate set.

**Personalisation, with the obvious caveat.** Learning that a shopper buys
formals in chiffon around wedding season, and leading with that, is a real
improvement — the same garment surfaced at the right moment converts far better
than a generic grid. Two guardrails though. First, **diversity and exploration**:
a pure exploit policy collapses into a filter bubble, so an ε-greedy or Thompson
sampling slot keeps novel inventory in rotation and keeps the training data from
eating its own tail. Second, **personalisation must serve the shopper, not just
basket size.** This build's whole argument is that trust converts better than
pressure; a recommender tuned purely to upsell would undo that. The honest
version is "we remembered what you like", not manufactured urgency.

**Evaluate it properly.** Offline recall@k and NDCG on held-out sessions to
sanity-check a candidate model, then an online A/B on the metric that actually
matters — add-to-cart rate *net of returns*. Offline gains in ranking metrics
routinely fail to survive contact with real traffic.

**Consent and privacy.** Behavioural profiling needs explicit consent capture,
a retention policy, and a way to browse without being profiled. That is a
prerequisite, not a follow-up.

**Prove it works.** The brief is about drop-off, so the honest question is
whether any of this converts. I'd instrument: panel-resolution rate (how many
shoppers ever supply a size or city), size-select → add-to-cart, alternatives
CTR by failure type, and restock-alert → return-visit-purchase. Then A/B the
gate, which is the single riskiest decision in the flow.

**Turn the "need it by" field into logistics intelligence.** This is the part I
would push hardest, because it is the one place the design generates data a
marketplace does not normally have. A stated deadline is a **first-party
declaration of intent** — not inferred from behaviour, volunteered. Aggregated,
it answers questions LAAM cannot currently ask:

- **What lead time do customers actually expect**, by city, category and season?
  Wedding and Eid demand is sharply seasonal, and a shopper buying formals in
  wedding season has a very different tolerance than one buying everyday lawn.
- **How often do we miss it?** The share of sessions where our promise lands
  after the requested date is a single honest number — call it the *confidence
  gap* — and it is directly attributable to a lane, a brand, or a category.
- **Where is the gap worth closing?** Ranking lanes by (gap frequency × lost
  basket value) turns a UX signal into a capital-allocation argument: which
  routes justify a faster courier tier, where to forward-deploy inventory, and
  which brands' dispatch SLAs are actually costing conversions.

There is a second, cheaper win in the same data. Logging **promised vs. actual**
arrival dates lets the estimator calibrate itself: `on_time_rate` stops being a
seeded constant and becomes an empirical per-brand, per-lane measurement, and
the transit table stops being static. The estimator gets more honest the longer
it runs, which is the right direction for a feature whose entire value is being
trusted.

**Product gaps.** Replace the openly-licensed stand-in imagery with real
catalogue photography — the pipeline already handles it, so this is a file swap;
caching for `/confidence` (currently one query per keystroke on the date field —
debounced client-side, but it should be cached server-side); serving images in
WebP/AVIF at multiple widths rather than raw JPEGs; i18n and Urdu support; and
proper consent capture before storing any email against a restock alert.

**Accessibility.** Keyboard navigation and ARIA are in place and the contrast
ratios hold, but it hasn't been screen-reader tested, and I wouldn't claim
conformance without that.

---

## 9. AI Usage

**Tool: Claude Code (Claude Opus 5).** A complete, append-only log of every
AI-assisted step is in [`AI_AUDIT.md`](AI_AUDIT.md), written as work happened
rather than reconstructed afterwards.

**What AI helped with:** researching LAAM's business and stack; drafting the
domain logic, tests and CSS; generating seed data; and acting as an adversarial
reviewer of its own design when asked to self-critique.

**What I directed or overruled:** the product thesis, the scope cuts, the stack
choice, and every design decision in `PLAN.md`'s decision log. I ran the code
rather than trusting it — which is how the bugs below were found.

### One example where I corrected AI output

The clearest case is the **stack recommendation**. The AI's first answer was
Next.js. I rejected it: my preference was FastAPI and I asked for an actual
evaluation rather than a default. On re-examination it found LAAM's own backend
posting specifies Python (Django/Flask/FastAPI) with PostgreSQL, and conceded
the original suggestion was a reflex "modern full-stack" default rather than a
decision reasoned from the brief. That reversal shaped the entire codebase.

### And one where the AI was factually wrong

Better evidence of *why* reviewing matters. The AI stated confidently that
Python 3.13's stdlib `zoneinfo` needed no extra dependency. That is **false on
Windows**, which ships no system tz database — the scaffold died with
`ZoneInfoNotFoundError: 'No time zone found with key Asia/Karachi'`. It was
caught only because the scaffold was **executed** rather than eyeballed.
`tzdata` is now pinned in `requirements.txt` with a comment explaining why.

Three further bugs were found the same way — by running the thing, not reading
it: `Size.S` leaking into customer-facing copy (Python 3.11 changed `__format__`
for str-mixin enums); a sold-out size painting **two** red rows because the
delivery failure was merely a consequence of the size failure; and the price card
quoting *"Delivery: Free · Total Rs 145,000"* for an address the delivery panel
directly above had just said we cannot ship to. All three are fixed, and the
last two now have regression tests.
