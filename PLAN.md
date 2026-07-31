# LAAM Assessment — Build Plan

**Status:** Design locked (rev 2), implementation in progress
**Last updated:** 2026-08-01

Working source of truth. Changes go here first, then into the code.

**Rev 2 changes:** location-first landing gate; brand filter added to browse;
GST-inclusive price breakdown; delivery fee shown as a *range* before a city is
known; "View alternatives" promoted to an always-available button; similarity
definition expanded; light-only minimal design.

---

## 1. The Brief, Condensed

LAAM is a South Asian fashion marketplace (1,000+ brands, 100k+ products, ships
to 100+ countries; top markets US, Canada, Middle East, Pakistan).

> "I like a product, but I am not fully confident whether it is available in my
> size, whether it can arrive on time, whether the price is final, or whether
> there are better alternatives."

Build a **small full-stack slice** that helps a customer decide with confidence.
Not a marketplace, not a checkout. **Time limit 3–4 hours.** Graded on judgment,
prioritisation, technical execution and pragmatic tradeoffs — not on volume.

---

## 2. Problem Understanding

The pain point: **a shopper's confidence collapses at the moment they try to turn
a general interest in a product into a specific decision for themselves** — their
size, their city, their deadline, their final price.

A standard product page answers questions about *the product*. It does not answer
questions about *this product, for me*. That gap is the drop-off.

### The thesis

> Confidence does not come from showing more numbers. It comes from being visibly
> honest about which numbers are actually yours.

**The rule (rev 2, sharpened):**

> Never render a precise-looking value that is really a guess. Where a value is
> genuinely uncertain, **express the uncertainty in the shape of the value
> itself** — a range — not only in a caption beneath it.

`Rs 199` before we know the city is a lie. `Free – Rs 4,200` is honest, because a
range announces itself as a range. This is what lets the price card stay useful
at cold start instead of sitting empty.

Two mechanisms follow:

**(a) Resolution states.** Every claim is unresolved, estimated (a labelled range
or default), or confirmed-for-you — and each is styled differently.

**(b) Failure → recovery coupling.** Each specific failure produces a specific
recovery. A sold-out size and a too-late delivery date are different problems and
must not yield the same generic "you may also like".

### Why we ask for the city instead of guessing it

Rev 1 planned to geo-guess the city and label it "estimated". Asking outright is
better on our own terms: **asked beats guessed.** It also moves confidence
upstream — once the city is known, the *listing* cards can carry real arrival
dates, so discovery itself becomes trustworthy rather than only the product page.

The gate is skippable. Forced gates lose browsers, and we already built the
unresolved state, so skipping costs nothing and demonstrates both paths.

---

## 3. Scope

### Building

- **Landing**: location gate (skippable), persisted to `localStorage`.
- **Browse**: grid with four filters — style, type, size, brand — each carrying
  availability so "is it in my size?" is answered before the click.
- **Product page**: image, price, size chips with per-size stock, and a
  **confidence card** holding delivery window + editable city, the full price
  breakdown, and a "View alternatives" button.
- **Alternatives**: one rail, two triggers (button, or an automatic
  constraint-filtered open when a check fails).
- **Restock alerts** for sold-out sizes.
- Unit tests on delivery and pricing; smoke tests on the API.
- README (9 sections) + `AI_AUDIT.md`.

### Explicitly not building

| Cut | Reason |
|---|---|
| Checkout, cart, payments, auth | Brief says not needed |
| Search | Four filters cover discovery; search is a different problem |
| Multi-currency | Rs throughout; FX is a rabbit hole |
| Real geo-IP | We ask instead — better on our own terms, and free |
| Dark mode | Minimal white was specified; one design done properly |
| Budget + country failure modes | Architecture generalises; 2 of 4 implemented |

---

## 4. User Flow

**1 · Landing (`/`).** One centred question — *"Where should we deliver?"* — with
a line explaining why we ask: *"so every price and delivery date you see is real
— no surprises at checkout."* A dropdown of 9 destinations, a Continue button,
and a quiet "Skip for now". The city persists; returning visitors are redirected
straight to browse and never see this again.

**2 · Browse (`/browse.html`).** Four filters:

- **Style** — All · Eastern · Western
- **Type** — All · Stitched · Unstitched
- **Size** — All · XS…XL
- **Brand** — All · (8 brands)

Style and type are independent axes rather than one crowded list (unstitched is
always eastern, so the combinations stay sensible). Cards show the item price and
an availability line; when a city is known they also show the arrival window.

**3 · Product (`/product.html?id=…`).** Image, brand, title, price, and size
chips with per-size stock. Beside them, the **confidence card**, ordered the way
a person actually decides:

1. **Your size** — reflects the chip selection, or prompts for one
2. **Arrives** — date window + the city, editable inline
3. **You'll pay** — full breakdown, GST disclosed, delivery included
4. **Action** — Add to cart / Notify me / Select a size
5. **View alternatives** — always available

**4 · Recovery.** See §5.

### Cold start on the product page (no city chosen)

This is the state a skipper lands in, and it must be *useful*, not blank:

| Row | Unresolved behaviour |
|---|---|
| Arrives | *"Ships from Lahore in 2 working days"* — dispatch is knowable without a city — plus **"Select your city for arrival dates"**. No date range is invented: "3–20 days" across Lahore→Canada is noise. |
| Delivery fee | A **range** across serviceable destinations, computed against this subtotal — e.g. *"Free within Pakistan · Rs 1,900–4,200 international"*. |
| Total | A **range**, styled as estimated, with the prompt to resolve it. |
| Subtotal | **Exact.** Item price and discount are fully knowable now, so they are stated plainly and anchor the card. |

Selecting the city in the card resolves all three rows in one request.

---

## 5. Failure → Recovery

Sold-out sizes are **marked but remain tappable**. Disabling them is a dead end:
the customer learns nothing and leaves. Tapping a struck-through chip means "M is
the size I want" — intent worth answering. The chip is labelled
`Sold out — tap for options` so the unusual affordance reads.

The rail has **two triggers, one mechanism**:

- **Button** — "View alternatives", always available, for the merely unsure.
- **Automatic** — a check fails, and the same rail opens hard-filtered by the
  constraint that failed, under a heading naming the problem.

When a check fails, exactly three things change; the image, description and brand
info do not move.

| Failure | Card row | Action becomes | Rail shows |
|---|---|---|---|
| Size sold out | `Size M — sold out` | *Notify me when M is back* | Similar, in stock **in M** |
| Every size sold out | `Sold out` | *Notify me* | Rail is the only path |
| Won't arrive by deadline | `Arrives Aug 18 — after Aug 15` | *See what arrives in time* | Items that **can** land in time |
| City unserviceable | `We don't deliver to Gwadar yet` | — | — (deferred) |
| Brand won't ship abroad | `This brand ships within Pakistan only` | *See brands that ship to UK* | Items from brands that **do** |
| No size selected | `Select a size` (unresolved) | *Select a size* (inert) | Button still works |

Every card states **why it is shown** — *"In stock in M · Chiffon · Arrives Sat 8
Aug"*. That labelling is the difference between a recommender and a confidence
tool.

**If nothing passes, say so.** *"Nothing similar in M right now."* Padding the
rail would undo the honesty the rest of the page is built on.

---

## 6. Tech Stack

**FastAPI + Pydantic + SQLite; plain HTML/CSS/ES modules, no build step.**
FastAPI serves the static files — one process, one command, no CORS.

LAAM's own backend posting asks for Python (Django/Flask/FastAPI) + PostgreSQL
and "clean, testable, maintainable backend code". Independently, FastAPI makes
backend design *visible*: Pydantic models are the data model, and `/docs` is a
free interactive API explorer for the reviewer.

**Vanilla-JS risk and mitigation:** one `state` object, one `render(state)`,
handlers that only mutate state and call render. Components are pure
`state → HTML string`. Choosing this deliberately is a stronger signal than
importing React would be.

---

## 7. Folder Structure

```
LAAM/
├── README.md · PLAN.md · AI_AUDIT.md · requirements.txt · .gitignore
├── backend/
│   ├── pytest.ini
│   ├── app/
│   │   ├── main.py        # app wiring, static mount, startup seed
│   │   ├── api.py         # all routes — thin, HTTP only
│   │   ├── schemas.py     # Pydantic contracts
│   │   ├── db.py          # sqlite schema + seed load
│   │   ├── repository.py  # the ONLY module writing SQL
│   │   └── domain/        # pure logic — no framework, no I/O
│   │       ├── pricing.py · delivery.py · alternatives.py · confidence.py
│   ├── seed/
│   │   ├── generate.py    # archetypes + edge cases -> products.json
│   │   ├── products.json · destinations.json
│   └── tests/
│       └── test_delivery.py · test_pricing.py · test_alternatives.py · test_api.py
└── frontend/
    ├── index.html         # landing — location gate
    ├── browse.html        # listing + four filters
    ├── product.html       # PDP + confidence card
    ├── css/styles.css     # light only, minimal white
    ├── img/placeholder.svg
    └── js/
        ├── api.js · store.js · format.js
        ├── landing.js · listing.js · product.js
        └── components/
            ├── sizeSelector.js · priceBreakdown.js · deliveryPanel.js
            ├── confidenceCard.js · alternativesRail.js
```

### Layer rules

**Backend.** `domain/` is pure — no FastAPI, no sqlite3. `repository.py` is the
only SQL. `api.py` is the only place status codes exist. Consequence: the
priority test suites need no fixtures, no client, no database.

**Frontend mirrors it.** `components/` are pure `state → HTML`. `api.js` is the
only `fetch`. Each page controller owns the single `state` and the single
`render()`, and is the only module touching the DOM.

---

## 8. Data Model

**products** — `id, title, brand, category (pret|formals|unstitched|west),
product_type (ready_to_wear|unstitched), price_pkr, discount_pct,
discount_ends_at, color, fabric, description_short, image_url, dispatch_city,
dispatch_days, stitching_days, ships_international, on_time_rate`

`description_short` is new in rev 2: the 4–5 words rendered in the placeholder
tile until real images land.

**variants** — `product_id, size, stock_qty`. Exposed to the client as a
**status** (`in_stock` / `low_stock` ≤3 / `out_of_stock`), never a raw number.
Inventory data is not customer data.

**destinations** — `name, zone, transit_days_min/max, shipping_fee_pkr,
free_shipping_threshold_pkr, serviceable`. Gwadar is seeded unserviceable.

**restock_alerts** — `product_id, size, email?, created_at`. Email optional;
production needs consent capture and a PII policy.

---

## 9. API

| Endpoint | Purpose |
|---|---|
| `GET /api/destinations` | Location picker, incl. unserviceable rows |
| `GET /api/brands` | Brand filter options with counts |
| `GET /api/products?style=&type=&size=&brand=&destination=` | Browse |
| `GET /api/products/{id}` | Detail with per-size status |
| `GET /api/products/{id}/confidence?size=&destination=&arrive_by=&stitching=` | Price + delivery + verdict |
| `GET /api/products/{id}/alternatives?size=&destination=&arrive_by=` | Ranked recovery |
| `POST /api/products/{id}/restock-alert` | Capture demand |

**Every query parameter is optional.** `/confidence` must answer correctly
knowing nothing — returning `unresolved` checks and fee *ranges*, never a 422.
That is the cold-start path, and the most-hit one.

---

## 10. Domain Logic

### `pricing.py` — GST-inclusive, ranged when unresolved

**Pakistani retail prices are GST-inclusive.** Adding 18% at the end would
misrepresent how every PK store prices *and* would make our own "no surprises"
promise the surprise. So GST is **disclosed, not added**:

```
Item price                Rs 8,900
Discount (15%)           −Rs 1,335
Subtotal                  Rs 7,565      ← exact, always knowable
Delivery to Lahore            FREE      ← over Rs 5,000 threshold
──────────────────────────────────
Total — what you pay      Rs 7,565
  incl. GST (18%)         Rs 1,154      ← component of the above
```

`gst = round(subtotal * 18 / 118)` — the tax *inside* a tax-inclusive price.

Exports are zero-rated, so **international destinations show no GST line**; they
get the disclosed duties note instead (assumption stated in the README).

**Unresolved (no city):** compute the fee for every serviceable destination at
this subtotal, then return `domestic_range` and `international_range` plus an
overall `total_range`. Free-shipping thresholds mean this often reads *"Free
within Pakistan · Rs 1,900–4,200 international"* — two useful facts rather than
one uselessly wide band.

An expired discount falls back to list price with **no strikethrough**.

### `delivery.py` — the centrepiece

The one module that must contain genuine logic, or the "can I trust the delivery
promise?" pillar is theatre.

```
1. order_day      = today, or next working day if past 17:00 Asia/Karachi
2. dispatch_ready = order_day + dispatch_days           (working days)
3. if unstitched and stitching requested:
       dispatch_ready += stitching_days                 (working days)
4. arrives_from   = dispatch_ready + transit_days_min   (working days)
   arrives_to     = dispatch_ready + transit_days_max   (working days)
```

Working days skip **Sundays** (PK couriers run Saturdays) and a public-holiday
table — **14 Aug 2026 (Independence Day)** sits inside the live estimate window,
so the calendar visibly moves dates in the demo rather than being an
unobservable claim.

`now` is **injected**, not read from the clock — the single most important
testability decision in the backend.

Always a range. Refuses rather than fabricates, with distinct reasons:
`no_size_selected`, `no_destination`, `out_of_stock`, `not_serviceable`,
`brand_no_international`.

### `alternatives.py` — what "similar" means

The question a shopper is really asking: *what else would do the job this product
was going to do?* In South Asian fashion the job is mostly **occasion** — a
wedding formal does not substitute for a lawn 3-piece at any price. We have no
occasion tag, but three fields approximate it well.

**Hard requirements — never violated:**

1. Same **category** — the identity of the garment's job
2. **In stock in the requested size**, when one is selected — an item you cannot
   wear is not an alternative, it is an ad
3. Not the same product; deliverable to the chosen city
4. Must not fail the **same check** the base product failed

**Ranking signals, by weight:**

| Signal | Weight | Why |
|---|---|---|
| Passes the failed check | 40 | The whole point of the rail |
| Price proximity `25 × (1 − |Δ|/base)`, clamped ≥0 | 25 | Strongest substitute signal; real alternatives sit within ~±30% |
| **Same fabric** | 15 | Domain-specific: fabric encodes season *and* occasion here — lawn = summer casual, chiffon/jamawar = formal, khaddar = winter. Two same-priced pret suits in lawn are far closer substitutes than lawn vs. velvet |
| Same product_type | 10 | Soft — crossing it is sometimes the *solution* (size sold out → unstitched has no size problem) |
| Arrives sooner or equal | 10 | Strictly more useful |
| Different brand | 5 | A genuine choice, not the same brand's adjacent SKUs |

**Colour is deliberately excluded.** Someone who liked teal is often happy with
rose; colour variety is a feature of a good rail, not a defect.

Deterministic and pure. Top 6. Empty when nothing passes.

### `confidence.py`

Folds `size` / `price` / `delivery` checks into a verdict and CTA.
**Precedence: fail beats unresolved beats ok** — one failure and one unknown is
`blocked`, not `incomplete`, because the failure is the more actionable fact.

CTA is derived server-side so the button can never disagree with the rows above.

---

## 11. Edge Case Register

| # | Case | Expected behaviour |
|---|---|---|
| 1 | No city, no size (cold start) | Ranges + prompts; never an error |
| 2 | Size sold out | Notify-me CTA, filtered rail |
| 3 | All sizes sold out | Product blocked; rail is the only path |
| 4 | Low stock ≤3 | "Only 2 left" — no timers, no view-counters |
| 5 | Unstitched | `Free Size`; stitching lead added to arrival |
| 6 | Discount expired | List price, **no** strikethrough |
| 7 | City unserviceable | Said plainly; no fabricated date |
| 8 | Brand won't ship abroad | Distinct from #7 — different recovery |
| 9 | Ordered after 17:00 cutoff | Clock starts next working day |
| 10 | Window spans 14 Aug | Holiday skipped, dates shift, reason shown |
| 11 | No alternatives pass | Honest empty state |
| 12 | `arrive_by` in the past | Validated, not crashed |
| 13 | Unknown product id | 404 with a usable message |
| 14 | **User skipped the gate** | Full ranged cold-start experience |
| 15 | **Unserviceable city chosen at the gate** | Told at the gate, not on every product page afterwards |
| 16 | **Stale `localStorage` city** no longer in destinations | Silently falls back to unresolved |
| 17 | **Filters combine to zero results** | Honest empty + one-click clear |
| 18 | **Size filter + unstitched items** | Unstitched is `Free Size` — stitched to measurement, so it *always* fits. Included under any size filter, labelled as such, rather than hidden |
| 19 | Subtotal just under free-shipping threshold | "Add Rs 320 for free delivery" |
| 20 | International destination | No GST line; duties note instead |

---

## 12. Seed Data

`seed/generate.py` holds the hand-written edge-case archetypes plus deterministic
filler, and writes `products.json` (~30 products, 8 brands, 4 categories). The
generator is committed so the data's intent is readable — the seed is a **design
artifact**, not filler: every row in §11 has a product that can trigger it.

---

## 13. Tests

1. **`test_delivery.py`** — cutoff rollover, Sunday skipping, 14 Aug holiday,
   stitching lead, range ordering, every refusal reason. Most branching, highest
   consequence, and the pillar the design rests on.
2. **`test_pricing.py`** — threshold boundary (exactly at / just under), expired
   discount, GST-inclusive maths, international zero-rating, unresolved ranges.
3. **`test_alternatives.py`** — hard filter never leaks a same-failure item;
   empty stays empty.
4. **`test_api.py`** — cold-start `/confidence` returns 200 with unresolved
   checks; unknown id 404s; raw stock never leaks.

---

## 14. Frontend State

```js
state = {
  product: null,
  selectedSize: null,
  destination: { value: null, source: "none" | "stored" | "user" },
  arriveBy: null,
  confidence: null,        // from the server — never computed client-side
  alternatives: [], railOpen: false, railReason: null,
  loading: {}, error: null,
}
```

The client **never computes a price or a date**. Those come from the server or
they do not appear — which is what prevents price-shown ≠ price-charged.

**Design:** minimal, white, light-only. Type-led, generous whitespace, hairline
borders, colour reserved for state (confirmed / estimated / unresolved / failed).
Mobile-first; the card drops below the sizes and the verdict sticks to the bottom.

**Placeholders:** each product renders its `description_short` (4–5 words) in a
tile tinted from its `color`, so the grid reads as a catalogue rather than a wall
of grey boxes. Real images later drop into `image_url` with zero rework.

---

## 15. Time Budget

| Block | Min |
|---|---|
| Scaffold + data model + seed | 40 |
| Domain logic + repository + API | 65 |
| Three pages, render loop, components | 95 |
| Tests + README + audit | 40 |
| **Total** | **~4h00** |

Rev 2 net change ≈ neutral: landing +20, GST +10, dark-mode removal −10,
alternatives-merge −15.

---

## 16. Known Risks

**The domain-specific parts are under time pressure.** Price breakdowns, size
stock and delivery dates are table stakes. Differentiation comes from the
resolution-state honesty, failure→recovery coupling, and LAAM specifics —
stitching lead time, GST-inclusive pricing, fabric-as-occasion in the similarity
model. **Protect those three above everything else.**

**The arrive-by field is the highest-variance idea** — genuine insight into
occasion-driven buying, or invented ceremony, depending on the reviewer. Optional
and never blocking.

**The gate adds a step before value.** Mitigated by skip + persistence, but it is
a real conversion cost and the README should say so rather than pretend otherwise.

---

## 17. AI Audit Policy

`AI_AUDIT.md` is append-only, written as work happens. README §9 needs one
concrete example of correcting or rejecting AI output; several real ones are
already logged, the strongest being the Windows `tzdata` failure (entry 12) —
a confidently stated, factually wrong claim caught only by executing the scaffold.

---

## 18. Decision Log

| # | Decision | Rationale |
|---|---|---|
| 1 | FastAPI over Next.js | Matches LAAM's stack; makes backend design visible; `/docs`; pytest |
| 2 | Vanilla JS over React | One stateful flow; state→render is a stronger signal |
| 3 | FastAPI serves static | One process, one command, no CORS |
| 4 | SQLite behind a repository | Data modelling graded; Postgres swap is one class |
| 5 | Price + delivery merged into `/confidence` | One input resolves both rows |
| 6 | Sold-out sizes tappable | Disabled is a dead end; the tap is intent |
| 7 | **Ask for the city, don't guess it** | Asked beats guessed; moves confidence upstream to the listing |
| 8 | Stock exposed as status, not quantity | Inventory data isn't customer data |
| 9 | Alternatives hard-filter before scoring | Never show something broken the same way |
| 10 | Range, never a single delivery date | A precise wrong date is worse than an honest range |
| 11 | **Uncertainty lives in the value's shape** | A range is honest where a point estimate is not — this is what keeps the cold-start card useful |
| 12 | **GST disclosed, never added** | PK prices are tax-inclusive; adding it would create the surprise we promise to prevent |
| 13 | **No arrival-date range before a city** | "3–20 days" is noise; dispatch time is knowable and useful instead |
| 14 | **Fabric weighted in similarity** | Encodes season and occasion in this market |
| 15 | **Unstitched included under any size filter** | Free Size is stitched to measurement, so it always fits — hiding it would suppress valid options |
| 16 | Alternatives = button + auto-trigger | One mechanism, two entry points; serves the unsure as well as the blocked |
| 17 | **Theme has three states, not two** | Auto / light / dark. Storing a choice only when one is made means a customer who never touches the toggle keeps following their OS, including when it flips at sunset |
| 18 | **Tiles carry a hue, not a colour** | Inline `hsl(...)` cannot respond to a theme switch; only `--tile-h` is inline, and CSS themes saturation and lightness |
| 19 | **The deadline verdict renders beside the date input** | It is a direct answer to what was just typed. Previously the panel derived its own severity from `delivery.available`, so a missed deadline still showed a green tick and the only signal was the rail heading far below |
| 20 | **"Why this date?" is collapsed by default** | The step breakdown is worth ~200px of card height; available on demand rather than charged to everyone |

---

## 19. Open Questions

- [x] ~~Real images to replace `description_short` placeholders.~~ Done: 29
      openly-licensed photographs fetched via Openverse by
      `seed/fetch_images.py`, attributed in `frontend/img/products/ATTRIBUTION.md`.
      LAAM's own catalogue images were deliberately **not** used — copyrighted,
      and attaching real garment photos to invented brands would undo the reason
      the brands were invented. The text tile survives as the fallback, so the
      image step stays optional.
- [ ] Swap the stand-ins for real catalogue photography when available — a file
      replacement plus `generate.py`, no code change.
- [ ] Keep the arrive-by field if the frontend block overruns?
      (Recommendation: keep — cheap once the estimator returns a range.)
