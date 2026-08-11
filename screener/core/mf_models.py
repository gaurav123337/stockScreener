"""Mutual-fund domain models — Pydantic for validation and serialization.

These are the Phase-3 additions: the scheme universe (AMFI NAV data), the
screener, the profiled recommendation flow, comparison, and the SIP
calculator. Field names are snake_case and mirror what the front end
consumes directly.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from screener.core.models import RiskLevel


class FundCategory(str, Enum):
    """Normalised SEBI scheme buckets used across the app.

    Kept deliberately coarse (the buckets a beginner actually chooses from)
    while the raw SEBI category string is preserved on each scheme.
    """
    LARGE = "large_cap"
    MID = "mid_cap"
    SMALL = "small_cap"
    FLEXI = "flexi_cap"
    MULTI = "multi_cap"
    VALUE = "value"
    ELSS = "elss"
    INDEX = "index"
    LIQUID = "liquid"
    DEBT = "debt"
    HYBRID = "hybrid"
    OTHER = "other"


CATEGORY_LABELS: dict[FundCategory, str] = {
    FundCategory.LARGE: "Large cap",
    FundCategory.MID: "Mid cap",
    FundCategory.SMALL: "Small cap",
    FundCategory.FLEXI: "Flexi cap",
    FundCategory.MULTI: "Multi cap",
    FundCategory.VALUE: "Value",
    FundCategory.ELSS: "ELSS (tax saver)",
    FundCategory.INDEX: "Index",
    FundCategory.LIQUID: "Liquid / overnight",
    FundCategory.DEBT: "Debt / bonds",
    FundCategory.HYBRID: "Hybrid / balanced",
    FundCategory.OTHER: "Other",
}


class FundReturns(BaseModel):
    """Compounded annual growth rate (CAGR) over standard lookbacks."""
    one_year: float | None = None
    three_year: float | None = None
    five_year: float | None = None
    ten_year: float | None = None
    since_inception: float | None = None


class FundRisk(BaseModel):
    """Risk-adjusted stats derived from NAV history (not a forecast)."""
    rating: int | None = Field(default=None, ge=1, le=5)   # 1 (low) .. 5 (high)
    rating_label: str | None = None                          # "Low" .. "Very high"
    volatility_annual: float | None = None                   # std-dev of daily returns, annualised
    sharpe: float | None = None                              # vs ~risk-free, from history
    sortino: float | None = None
    max_drawdown: float | None = None


class FundScheme(BaseModel):
    """One scheme in the searchable universe (direct-plan preferred)."""
    scheme_code: int
    scheme_name: str
    fund_house: str | None = None
    category: FundCategory = FundCategory.OTHER
    sebi_category: str | None = None        # raw SEBI category string
    is_direct: bool = False
    is_growth: bool = False
    is_elss: bool = False
    nav: float | None = None
    nav_date: str | None = None             # "2026-08-05"
    isin_growth: str | None = None

    # Curated metadata (not available from AMFI NAV file) — optional.
    expense_ratio: float | None = None      # % p.a., direct plan
    aum_cr: float | None = None             # crore rupees
    launch_date: str | None = None          # "2013-01-01"
    fund_manager: str | None = None
    exit_load: str | None = None            # e.g. "1% if redeemed within 1 year"

    # Derived analytics (computed from history when available).
    returns: FundReturns = Field(default_factory=FundReturns)
    risk: FundRisk = Field(default_factory=FundRisk)
    fund_age_years: float | None = None

    # Freshness — when this scheme's data was pulled.
    data_as_of: datetime | None = None
    source: str = "amfi"
    error: str | None = None

    @property
    def badges(self) -> list[str]:
        """Plain-language badges shown on cards (ELSS, direct, etc.)."""
        badges: list[str] = []
        if self.is_elss:
            badges.append("Tax saver (ELSS)")
        if self.is_direct:
            badges.append("Direct plan")
        if self.exit_load:
            badges.append("Exit load applies")
        return badges


class FundScreenerRequest(BaseModel):
    """Query model for the fund screener (mirrors query params)."""
    category: FundCategory | None = None
    max_expense_ratio: float | None = None   # % p.a.
    min_aum_cr: float | None = None
    min_return_1y: float | None = None       # e.g. 12 (percent)
    min_return_3y: float | None = None
    min_return_5y: float | None = None
    max_risk_rating: int | None = Field(default=None, ge=1, le=5)
    min_fund_age_years: float | None = None
    manager: str | None = None               # free-text match on fund_manager
    elss_only: bool = False
    direct_only: bool = True
    sort_by: str = "sharpe"                  # sharpe | sortino | returns_1y | returns_3y | returns_5y | expense_ratio | aum | nav | name
    sort_dir: str = "desc"
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class FundScreenerResult(BaseModel):
    """Result of screening the cached scheme universe."""
    items: list[FundScheme] = Field(default_factory=list)
    total: int = 0
    categories: list[dict[str, str]] = Field(default_factory=list)
    sort_by: str = "sharpe"
    sort_dir: str = "desc"
    data_as_of: datetime | None = None
    refreshed_at: datetime = Field(default_factory=datetime.now)
    source: str = "amfi"
    stale: bool = False
    note: str | None = None


class FundAllocation(BaseModel):
    """One piece of a profiled fund basket."""
    category: FundCategory
    weight: float = 0.0                     # share of the fund sleeve (0..1)
    advice: str = ""                        # "60% index + 40% hybrid" style guidance


class FundRecommendation(BaseModel):
    """A concrete scheme picked for a risk profile + goal."""
    scheme_code: int
    scheme_name: str
    fund_house: str | None = None
    category: FundCategory = FundCategory.OTHER
    sebi_category: str | None = None
    is_elss: bool = False
    weight: float = 0.0                     # share of the fund sleeve
    nav: float | None = None
    nav_date: str | None = None
    expense_ratio: float | None = None
    aum_cr: float | None = None
    returns: FundReturns = Field(default_factory=FundReturns)
    risk: FundRisk = Field(default_factory=FundRisk)
    badges: list[str] = Field(default_factory=list)
    plain: str = ""                         # why this fund, in plain language


class FundBasket(BaseModel):
    """A profiled mutual-fund basket for a risk profile + goal."""
    risk_level: RiskLevel
    risk_label: str = ""
    goal: str = ""
    monthly_amount: float = 0.0
    horizon_years: int = 0
    split: list[FundAllocation] = Field(default_factory=list)
    schemes: list[FundRecommendation] = Field(default_factory=list)
    expected_return_range: list[float] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)
    data_as_of: datetime | None = None
    source: str = "amfi"


class FundComparison(BaseModel):
    """2–4 schemes compared side by side."""
    codes: list[int] = Field(default_factory=list)
    schemes: list[FundScheme] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)


class SipResult(BaseModel):
    """SIP / lumpsum / step-up projection (educational, not a forecast)."""
    mode: str                               # sip | lumpsum | sip_stepup
    monthly_amount: float = 0.0             # base monthly amount (SIP modes)
    lumpsum_amount: float = 0.0             # one-time amount (lumpsum mode)
    years: int = 0
    step_up_pct: float = 0.0                # annual % increase (sip_stepup)
    assumed_return_pct: float = 0.0         # annual % used (clearly an assumption)
    invested: float = 0.0                   # total money put in
    future_value: float = 0.0               # projected corpus
    table: list[dict[str, Any]] = Field(default_factory=list)  # yearly rows


class FundDetail(BaseModel):
    """Full scheme detail including historical NAV series."""
    scheme: FundScheme = Field(default_factory=FundScheme)
    history: list[dict[str, Any]] = Field(default_factory=list)   # [{date, nav}]
    is_nfo: bool = False                    # launched very recently
    generated_at: datetime = Field(default_factory=datetime.now)
