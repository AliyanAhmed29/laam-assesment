"""API contracts.

Single job: define the shapes that cross the HTTP boundary. No logic lives here.

These models are deliberately the most readable file in the backend — with
FastAPI's generated `/docs`, they *are* the API documentation. See PLAN.md §8-9.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


# --------------------------------------------------------------------------
# Enumerations — the domain vocabulary
# --------------------------------------------------------------------------


class Category(str, Enum):
    PRET = "pret"
    UNSTITCHED = "unstitched"
    FORMALS = "formals"
    WEST = "west"


class Style(str, Enum):
    """Browse filter axis. Derived from category rather than stored: everything
    that is not western is eastern, and unstitched is always eastern."""

    EASTERN = "eastern"
    WESTERN = "western"


class ProductType(str, Enum):
    """The second, independent browse axis — and what drives whether stitching
    lead time applies to the delivery estimate."""

    READY_TO_WEAR = "ready_to_wear"
    UNSTITCHED = "unstitched"


class Size(str, Enum):
    XS = "XS"
    S = "S"
    M = "M"
    L = "L"
    XL = "XL"
    FREE = "Free Size"  # unstitched fabric is cut to measurement


class StockStatus(str, Enum):
    """What the customer is told. Raw quantity is inventory data, not customer
    data, and never reaches the client (PLAN.md decision #8)."""

    IN_STOCK = "in_stock"
    LOW_STOCK = "low_stock"
    OUT_OF_STOCK = "out_of_stock"


class CheckStatus(str, Enum):
    """The three resolution states. `UNRESOLVED` is the cold-start default and
    the most-hit path — a legitimate answer, never an error."""

    OK = "ok"
    FAIL = "fail"
    UNRESOLVED = "unresolved"


class Verdict(str, Enum):
    READY = "ready"
    BLOCKED = "blocked"
    INCOMPLETE = "incomplete"


class Cta(str, Enum):
    ADD_TO_CART = "add_to_cart"
    NOTIFY_ME = "notify_me"
    SEE_ALTERNATIVES = "see_alternatives"
    SELECT_SIZE = "select_size"


class Zone(str, Enum):
    DOMESTIC_METRO = "domestic_metro"
    DOMESTIC_OTHER = "domestic_other"
    INTL_GCC = "intl_gcc"
    INTL_WEST = "intl_west"


class UnavailableReason(str, Enum):
    """Why no delivery estimate could be produced.

    Distinct machine-readable reasons, because each drives a different recovery.
    Refusing to estimate is a feature: a fabricated date is worse than a blank.
    """

    NO_SIZE_SELECTED = "no_size_selected"
    NO_DESTINATION = "no_destination"
    OUT_OF_STOCK = "out_of_stock"
    NOT_SERVICEABLE = "not_serviceable"
    BRAND_NO_INTERNATIONAL = "brand_no_international"


class ValueSource(str, Enum):
    """How a displayed value was arrived at — the honesty mechanism made
    structural. The client styles ESTIMATED differently from CONFIRMED so a
    guess never masquerades as a fact."""

    UNRESOLVED = "unresolved"
    ESTIMATED = "estimated"
    CONFIRMED = "confirmed"


# --------------------------------------------------------------------------
# Products
# --------------------------------------------------------------------------


class SizeAvailability(BaseModel):
    size: Size
    status: StockStatus
    units_left: int | None = Field(
        default=None, description="Only when low_stock. Honest scarcity."
    )


class ProductCard(BaseModel):
    """Listing view. Carries availability so the browse page answers 'is it in
    my size?' before the click rather than after it."""

    id: str
    title: str
    brand: str
    category: Category
    style: Style
    product_type: ProductType
    color: str
    fabric: str
    description_short: str = Field(
        description="4-5 words, rendered in the placeholder tile until real "
        "imagery lands. Swapping in photos is then drop-in."
    )
    image_url: str
    price_pkr: int
    discounted_price_pkr: int
    discount_pct: int = Field(description="0 when absent or expired.")
    available_sizes: list[Size]
    sold_out: bool


class ProductDetail(ProductCard):
    dispatch_city: str
    dispatch_days: int
    stitching_days: int
    ships_international: bool
    on_time_rate: float = Field(ge=0, le=1)
    sizes: list[SizeAvailability]


class BrandOption(BaseModel):
    """Brand filter option. Counts let the UI grey out brands with nothing to
    show under the current filters instead of offering a dead end."""

    name: str
    product_count: int


class Destination(BaseModel):
    name: str
    zone: Zone
    serviceable: bool
    is_international: bool


# --------------------------------------------------------------------------
# Confidence — price + delivery + verdict, in one response
# --------------------------------------------------------------------------


class MoneyRange(BaseModel):
    """Uncertainty expressed in the *shape* of the value.

    This is what lets the price card stay useful before a city is known:
    `Rs 199` would be a lie, `Free – Rs 4,200` is honest, because a range
    announces itself as a range (PLAN.md decision #11).
    """

    min_pkr: int
    max_pkr: int


class PriceBreakdown(BaseModel):
    """'What will I actually pay?' answered literally."""

    list_price_pkr: int
    discount_pct: int
    discount_active: bool
    discount_amount_pkr: int
    subtotal_pkr: int = Field(
        description="Always exact — item price and discount are knowable "
        "without a destination, so this anchors the card at cold start."
    )
    deliverable: bool = Field(
        default=True,
        description="False when we cannot ship to the chosen destination at "
        "all. There is then no total to quote, and offering one would "
        "contradict the delivery panel sitting directly above it.",
    )

    # Resolved (destination known)
    shipping_fee_pkr: int | None = None
    total_pkr: int | None = None

    # Unresolved (no destination) — ranges, never point estimates
    domestic_shipping_range: MoneyRange | None = None
    international_shipping_range: MoneyRange | None = None
    total_range: MoneyRange | None = None

    free_shipping_threshold_pkr: int | None = None
    amount_to_free_shipping_pkr: int | None = Field(
        default=None, description="Gap to free delivery. Information, not a nudge."
    )

    gst_pkr: int | None = Field(
        default=None,
        description="GST *included* in the subtotal, never added on top — "
        "Pakistani retail prices are tax-inclusive. None for exports, which "
        "are zero-rated.",
    )
    gst_rate_pct: int = 18
    duties_note: str | None = Field(
        default=None, description="Disclosed, never computed, for exports."
    )
    source: ValueSource


class DeliveryStep(BaseModel):
    """One line of the 'why this date' breakdown. Showing the working makes the
    promise auditable instead of magical."""

    label: str
    days: int
    ends_on: date


class DeliveryEstimate(BaseModel):
    available: bool
    reason: UnavailableReason | None = None

    arrives_from: date | None = None
    arrives_to: date | None = None
    steps: list[DeliveryStep] = []
    skipped_dates: list[date] = Field(
        default=[], description="Sundays and public holidays excluded from transit."
    )
    dispatch_note: str | None = Field(
        default=None,
        description="Knowable without a destination, e.g. 'Ships from Lahore in "
        "2 working days'. Deliberately shown instead of an arrival range: "
        "'3-20 days' across Lahore-to-Canada would be noise.",
    )
    on_time_rate: float | None = None
    source: ValueSource = ValueSource.UNRESOLVED


class Check(BaseModel):
    id: str  # "size" | "price" | "delivery"
    status: CheckStatus
    label: str  # human-readable, already resolved server-side
    detail: str | None = None


class ConfidenceResponse(BaseModel):
    """The aggregate. One user input (destination) resolves two rows, so price
    and delivery are answered together in a single round trip (decision #5)."""

    product_id: str
    size: Size | None
    destination: str | None
    arrive_by: date | None

    price: PriceBreakdown
    delivery: DeliveryEstimate
    checks: list[Check]
    verdict: Verdict
    cta: Cta
    failed_checks: list[str] = Field(
        default=[], description="Drives the hard filter on the alternatives rail."
    )


# --------------------------------------------------------------------------
# Alternatives
# --------------------------------------------------------------------------


class AlternativeCard(ProductCard):
    """`reasons` is what separates a confidence tool from a recommender: each
    card states why it is on screen, e.g. 'In stock in M', 'Arrives Sat 8 Aug'."""

    reasons: list[str]
    score: float = Field(description="Exposed for debugging and test assertions.")


class AlternativesResponse(BaseModel):
    items: list[AlternativeCard]
    filtered_on: list[str] = Field(
        default=[], description="Which failed constraints became hard filters."
    )
    empty_reason: str | None = Field(
        default=None,
        description="Set when nothing passed. We say so rather than padding.",
    )


# --------------------------------------------------------------------------
# Restock alerts
# --------------------------------------------------------------------------


class RestockAlertRequest(BaseModel):
    size: Size
    email: EmailStr | None = Field(
        default=None,
        description=(
            "Optional by design. Demo storage only — production needs explicit "
            "consent capture and PII handling. See README."
        ),
    )


class RestockAlertResponse(BaseModel):
    created: bool
    message: str
