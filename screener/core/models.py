"""Domain models — Pydantic for validation, serialization, and type safety.

These replace the ad-hoc dicts and dataclasses scattered through the codebase.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, computed_field


class Action(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class Outcome(str, Enum):
    TARGET_HIT = "target_hit"
    STOP_HIT = "stop_hit"
    CORRECT = "correct"
    WRONG = "wrong"


class StockMetrics(BaseModel):
    """Fundamental + technical metrics for a stock."""
    # Fundamentals
    pe: float | None = None
    peg: float | None = None
    roe: float | None = None
    debt_to_equity: float | None = None
    sector: str | None = None
    name: str | None = None

    # Technical
    rsi: float | None = None
    sma50: float | None = None
    sma200: float | None = None
    atr: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    volume: float | None = None
    volume_avg_20: float | None = None
    high_52w: float | None = None
    low_52w: float | None = None

    # Derived flags (computed from price + technicals)
    above_sma50: bool = False
    above_sma200: bool = False
    golden_cross: bool = False
    near_52w_high: bool = False
    near_52w_low: bool = False


class DriverScore(BaseModel):
    """One plain-language driver on a thesis card (Trend/Momentum/Value/Quality)."""
    key: str                       # trend | momentum | value | quality
    label: str                     # "Trend"
    score: float
    positive: bool | None = None   # None when neutral
    plain: str                     # one-line beginner explanation
    why: list[str] = Field(default_factory=list)  # plain-language evidence


class Thesis(BaseModel):
    """Phase-2 beginner-first additions to a recommendation."""
    risk_badge: str | None = None            # "Low" | "Medium" | "High"
    portfolio_role: str | None = None        # e.g. "Core holding"
    allocation_size: float | None = None     # suggested % of equity sleeve (0..1)
    drivers: list[DriverScore] = Field(default_factory=list)
    what_could_go_wrong: list[str] = Field(default_factory=list)
    thesis: str | None = None                # 2-3 sentence plain-language summary


class Recommendation(BaseModel):
    """A complete trade recommendation."""
    symbol: str
    action: Action
    score: float = Field(..., ge=-100, le=100)
    price: float
    entry: float | None = None
    target: float | None = None
    stop_loss: float | None = None
    risk_reward: float | None = None
    reasons: list[str] = Field(default_factory=list)
    metrics: StockMetrics = Field(default_factory=StockMetrics)
    error: str | None = None
    analyzed_at: datetime = Field(default_factory=datetime.now)
    # Phase-1 trust additions: how much the pillars agree + the per-pillar
    # score breakdown. Explicitly NOT a "probability of profit" — it is a
    # transparency measure (agreement, signal strength, data freshness).
    confidence: float | None = Field(default=None, ge=0, le=1)
    pillars: dict[str, float] = Field(default_factory=dict)
    # Phase-2 beginner-first additions: plain-language thesis card data.
    thesis_data: Thesis = Field(default_factory=Thesis)

    @computed_field
    @property
    def is_valid(self) -> bool:
        return self.error is None

    def to_scan_row(self) -> dict[str, Any]:
        """Flatten for scan/filter usage (backward compatible)."""
        m = self.metrics
        return {
            "symbol": self.symbol,
            "name": (m.name or "")[:28],
            "sector": m.sector,
            "action": self.action.value,
            "score": self.score,
            "confidence": self.confidence,
            "pillars": self.pillars,
            "price": self.price,
            "entry": self.entry,
            "target": self.target,
            "stop_loss": self.stop_loss,
            "rr": self.risk_reward,
            "rsi": m.rsi,
            "pe": m.pe,
            "peg": m.peg,
            "roe": m.roe,
            "debt_to_equity": m.debt_to_equity,
            "sma50": m.sma50,
            "sma200": m.sma200,
            "atr": m.atr,
            "above_sma50": m.above_sma50,
            "above_sma200": m.above_sma200,
            "golden_cross": m.golden_cross,
            "near_52w_high": m.near_52w_high,
            "near_52w_low": m.near_52w_low,
            "reasons": self.reasons,
            "error": self.error,
            "risk_badge": self.thesis_data.risk_badge,
            "portfolio_role": self.thesis_data.portfolio_role,
            "allocation_size": self.thesis_data.allocation_size,
            "drivers": [d.model_dump() for d in self.thesis_data.drivers],
            "what_could_go_wrong": self.thesis_data.what_could_go_wrong,
            "thesis": self.thesis_data.thesis,
        }


class ScanResult(BaseModel):
    """Result of scanning a universe of stocks."""
    matched: list[Recommendation] = Field(default_factory=list)
    failed: list[dict[str, str]] = Field(default_factory=list)
    total_scanned: int = 0
    filter_applied: str | None = None


class PredictionRecord(BaseModel):
    """A logged prediction for later verification."""
    ts: datetime
    symbol: str
    action: Action
    price_at_call: float
    target: float | None = None
    stop_loss: float | None = None
    horizon_days: int = 30
    evaluated: bool = False
    eval_date: datetime | None = None
    price_at_eval: float | None = None
    outcome: Outcome | None = None
    return_pct: float | None = None
    score: float | None = None
    confidence: float | None = None
    user_id: str | None = None

    def return_at(self, price: float) -> float:
        """Directional return at ``price`` — positive means the call was right."""
        if self.action == Action.BUY:
            return (price - self.price_at_call) / self.price_at_call
        if self.action == Action.SELL:
            return (self.price_at_call - price) / self.price_at_call
        # HOLD: penalise large moves in either direction (the call was "stay put").
        return -abs((price - self.price_at_call) / self.price_at_call)

    def directional_win(self, price: float, flat_band: float = 0.02) -> bool:
        """True when the signal's expectation at ``price`` was met.

        BUY/SELL are judged directionally; HOLD is judged as "stayed flat"
        (within ``flat_band`` of the call price), which is the honest reading
        of a neutral signal.
        """
        ret = self.return_at(price)
        if self.action == Action.HOLD:
            return abs(ret) <= flat_band
        return ret > 0


class HorizonStats(BaseModel):
    """Aggregate backtest statistics for one evaluation horizon."""
    horizon_days: int
    n: int = 0
    hit_rate: float | None = None          # % of signals correct
    avg_return: float | None = None        # mean directional return
    avg_win: float | None = None           # mean return of winning signals
    avg_loss: float | None = None          # mean return of losing signals
    max_drawdown: float | None = None      # worst peak-to-trough (fraction)
    benchmark_avg_return: float | None = None
    vs_benchmark: float | None = None      # avg_return - benchmark_avg_return
    by_action: dict[str, dict[str, Any]] = Field(default_factory=dict)


class VerificationReport(BaseModel):
    """Summary of prediction verification (rolling, dated)."""
    evaluated_now: int = 0
    total_evaluated: int = 0
    overall_hit_rate: float | None = None
    by_action: dict[str, dict[str, Any]] = Field(default_factory=dict)
    horizons: list[HorizonStats] = Field(default_factory=list)
    benchmark_symbol: str | None = None
    window_start: datetime | None = None
    generated_at: datetime = Field(default_factory=datetime.now)


class BacktestReport(BaseModel):
    """Published walk-forward track record (Stockopedia-style evidence)."""
    status: str = "ok"
    generated_at: datetime = Field(default_factory=datetime.now)
    window_start: datetime
    window_end: datetime
    universe: list[str] = Field(default_factory=list)
    universe_size: int = 0
    horizons: list[HorizonStats] = Field(default_factory=list)
    methodology: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RiskLevel(str, Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class RiskProfile(BaseModel):
    """A user's onboarding risk profile + suggested asset split."""
    level: RiskLevel
    label: str
    summary: str
    asset_split: dict[str, float]           # equity_delivery / mutual_funds / liquid
    expected_return_range: list[float] = Field(default_factory=list)  # [low, high] p.a.
    answers: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)


class PlanBasketItem(BaseModel):
    """One holding in a goal-based starter basket."""
    symbol: str
    name: str | None = None
    sector: str | None = None
    role: str = ""
    weight: float = 0.0          # share of the equity sleeve (0..1)
    score: float = 0.0
    action: Action = Action.HOLD
    price: float = 0.0
    plain: str = ""              # why this stock, in plain language
    risk_badge: str | None = None
    driver_highlights: list[str] = Field(default_factory=list)


class InvestmentPlan(BaseModel):
    """A goal-based starter basket + asset split for a beginner."""
    risk_level: RiskLevel
    risk_label: str = ""
    goal: str = ""
    monthly_amount: float = 0.0
    horizon_years: int = 0
    asset_split: dict[str, float] = Field(default_factory=dict)
    basket: list[PlanBasketItem] = Field(default_factory=list)
    mutual_funds: list[str] = Field(default_factory=list)
    expected_return_range: list[float] = Field(default_factory=list)
    conservative_return_range: list[float] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)
    # Phase-3: concrete direct-plan fund schemes for the fund sleeve
    # (FundRecommendation payloads, kept as dicts to avoid a model dependency
    # cycle between core.models and core.mf_models).
    fund_schemes: list[dict[str, Any]] = Field(default_factory=list)
    fund_data_as_of: datetime | None = None


class LearnResult(BaseModel):
    """Result of knowledge ingestion."""
    ok: bool = True
    ingested: list[str] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    rules_added: int = 0
    saved_as: str | None = None
    error: str | None = None


class BrokerStatus(BaseModel):
    """Broker connection status."""
    connected: bool = False
    library_installed: bool = False
    library: str = ""
    credentials_present: bool = False


class Holding(BaseModel):
    """Normalized broker holding."""
    symbol: str
    quantity: float
    average_price: float
    current_price: float | None = None
    pnl: float | None = None
    broker: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict, exclude=True)
