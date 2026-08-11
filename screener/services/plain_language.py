"""Plain-language layer for beginner-first UX.

Two jobs:
1. A glossary of every metric a beginner might see, written the way Varsity
   or Stockopedia would — "P/E = how much you pay for every ₹1 of profit".
2. Thesis-card enrichment: turning the raw pillar scores + reasons into
   plain-language drivers (Trend / Momentum / Value / Quality), a risk badge,
   a portfolio role, a suggested allocation, a "what could go wrong" box and
   a short plain-language summary.

All enrichment is derived from data the engine already produced (reasons,
pillars, metrics) — nothing new is asserted about the market.
"""
from __future__ import annotations

from screener.core.models import Action, DriverScore, Recommendation, Thesis

# --------------------------------------------------------------------------- #
# Glossary — plain-language definitions keyed by metric name (see /api/glossary)
# --------------------------------------------------------------------------- #

GLOSSARY: dict[str, dict[str, str]] = {
    "score": {
        "term": "Signal Score",
        "plain": (
            "One number from -100 to +100 that sums up what the engine sees. "
            "Positive = the stock looks promising, negative = it looks risky."
        ),
    },
    "confidence": {
        "term": "Confidence",
        "plain": (
            "How strongly the different checkpoints agree with each other. "
            "It is NOT a probability of profit — it just tells you how much the "
            "signals back each other up."
        ),
    },
    "pe": {
        "term": "P/E ratio",
        "plain": (
            "How much you pay for every ₹1 of profit the company makes. "
            "A lower P/E usually means the stock is cheaper relative to its earnings."
        ),
    },
    "peg": {
        "term": "PEG ratio",
        "plain": (
            "The P/E ratio compared with how fast the company is growing. "
            "Below 1 = the growth may not be fully priced in yet."
        ),
    },
    "roe": {
        "term": "Return on Equity (ROE)",
        "plain": (
            "How much profit the company earns for every ₹100 the owners have put in. "
            "Higher and steady is usually a sign of a quality business."
        ),
    },
    "debt_to_equity": {
        "term": "Debt to Equity",
        "plain": (
            "How much the company owes compared with what its owners have invested. "
            "Very high debt means the company must pay interest before shareholders "
            "see anything."
        ),
    },
    "rsi": {
        "term": "RSI",
        "plain": (
            "A gauge of how quickly the price has moved recently. "
            "Above 70 = the stock may be overbought (expensive short-term), "
            "below 30 = oversold (possibly cheap short-term)."
        ),
    },
    "sma50": {
        "term": "50-day average price",
        "plain": (
            "The average price of the stock over the last 50 trading days. "
            "Price above it = the stock is above its recent average."
        ),
    },
    "sma200": {
        "term": "200-day average price",
        "plain": (
            "The average price of the stock over the last 200 trading days. "
            "It shows the longer-term trend."
        ),
    },
    "golden_cross": {
        "term": "Golden cross",
        "plain": (
            "When the 50-day average moves above the 200-day average. "
            "A classic sign of a strengthening longer-term trend."
        ),
    },
    "atr": {
        "term": "Daily volatility (ATR)",
        "plain": (
            "How much the stock price typically moves in a day. "
            "A bigger number means a bumpier, riskier ride."
        ),
    },
    "volume": {
        "term": "Volume",
        "plain": (
            "How many shares are being traded. Rising volume on a move up usually "
            "means the move has real support behind it."
        ),
    },
    "high_52w": {
        "term": "52-week high",
        "plain": "The highest price the stock touched in the last year.",
    },
    "low_52w": {
        "term": "52-week low",
        "plain": "The lowest price the stock touched in the last year.",
    },
    "near_52w_high": {
        "term": "Near 52-week high",
        "plain": "The stock is within a few percent of its best price in the last year.",
    },
    "near_52w_low": {
        "term": "Near 52-week low",
        "plain": (
            "The stock is near its worst price in the last year — the downtrend "
            "may continue."
        ),
    },
    "entry": {
        "term": "Entry price",
        "plain": "A sensible price to start buying at, based on current levels.",
    },
    "target": {
        "term": "Target price",
        "plain": (
            "The price the engine thinks the stock could reach if the current "
            "trend continues."
        ),
    },
    "stop_loss": {
        "term": "Stop-loss",
        "plain": (
            "The price at which you should exit to protect yourself if the stock "
            "falls against you. A safety net, not a guarantee."
        ),
    },
    "rr": {
        "term": "Risk : Reward",
        "plain": (
            "How much you could gain compared with how much you risk. "
            "2.0 means you aim to gain ₹2 for every ₹1 you could lose."
        ),
    },
    "action": {
        "term": "Call",
        "plain": (
            "The engine's plain-language verdict: BUY (looks good), SELL (looks "
            "risky) or HOLD (mixed — wait for a clearer signal)."
        ),
    },
    "asset_split": {
        "term": "Asset split",
        "plain": (
            "How your money is divided between shares, mutual funds and safer "
            "liquid options, based on how much risk suits you."
        ),
    },
    "weight": {
        "term": "Weight",
        "plain": "What fraction of your money should go into each holding.",
    },
}


def glossary() -> dict[str, dict[str, str]]:
    """Return a copy of the glossary (JSON-safe, no aliasing surprises)."""
    return {key: dict(value) for key, value in GLOSSARY.items()}


def term_plain(term: str) -> str | None:
    entry = GLOSSARY.get(term)
    return entry["plain"] if entry else None


# --------------------------------------------------------------------------- #
# Thesis-card enrichment
# --------------------------------------------------------------------------- #

_TREND_KEYWORDS = ("DMA", "cross", "uptrend", "downtrend")
_MOMENTUM_KEYWORDS = ("RSI", "MACD", "Volume", "participation", "momentum", "overbought", "oversold")
_VALUE_KEYWORDS = ("PEG", "P/E", "undervalued", "expensive", "earnings growth", "low vs")
_QUALITY_KEYWORDS = ("ROE", "Debt/Equity", "quality", "leverage")


def _split_reasons(reasons: list[str]) -> dict[str, list[str]]:
    """Bucket raw engine reasons into trend/momentum/value/quality buckets."""
    buckets: dict[str, list[str]] = {"trend": [], "momentum": [], "value": [], "quality": []}
    for reason in reasons:
        if any(k in reason for k in _TREND_KEYWORDS):
            buckets["trend"].append(reason)
        if any(k in reason for k in _MOMENTUM_KEYWORDS):
            buckets["momentum"].append(reason)
        if any(k in reason for k in _VALUE_KEYWORDS):
            buckets["value"].append(reason)
        if any(k in reason for k in _QUALITY_KEYWORDS):
            buckets["quality"].append(reason)
    return buckets


def _plain_bucket(bucket: str, score: float) -> str:
    """One-line beginner explanation for a driver bucket."""
    if bucket == "trend":
        return (
            "Is the price moving up or down over time? (Price vs its 50 & 200-day averages)"
            if score > 0
            else "Is the price moving up or down over time? (It's currently below its averages)"
        )
    if bucket == "momentum":
        return (
            "Is buying pressure building right now? (RSI, MACD and trading volume)"
            if score > 0
            else "Is buying pressure building right now? (RSI, MACD and trading volume are weak)"
        )
    if bucket == "value":
        return (
            "Is the price fair or cheap for what the company earns? (P/E vs growth)"
            if score > 0
            else "Is the price fair or cheap for what the company earns? (It looks on the expensive side)"
        )
    return (
        "How strong and stable is the business itself? (Returns on invested money and debt)"
        if score > 0
        else "How strong and stable is the business itself? (Weak returns or high debt)"
    )


def build_drivers(pillars: dict[str, float], reasons: list[str]) -> list[DriverScore]:
    """Build the four plain-language driver breakdowns from engine output."""
    buckets = _split_reasons(reasons)
    fundamental = pillars.get("fundamentals", 0.0)
    value_reasons = buckets["value"]
    quality_reasons = buckets["quality"]
    n_fund = len(value_reasons) + len(quality_reasons)
    value_score = (
        round(fundamental * (len(value_reasons) / n_fund), 2) if n_fund else 0.0
    )
    quality_score = (
        round(fundamental * (len(quality_reasons) / n_fund), 2) if n_fund else 0.0
    )

    momentum_total = pillars.get("momentum", 0.0) + pillars.get("volume", 0.0)

    specs = [
        ("trend", "Trend", pillars.get("trend", 0.0), buckets["trend"]),
        ("momentum", "Momentum", momentum_total, buckets["momentum"]),
        ("value", "Value", value_score, value_reasons),
        ("quality", "Quality", quality_score, quality_reasons),
    ]

    drivers: list[DriverScore] = []
    for key, label, score, why in specs:
        drivers.append(
            DriverScore(
                key=key,
                label=label,
                score=round(float(score), 2),
                positive=None if score == 0 else score > 0,
                plain=_plain_bucket(key, score),
                why=why,
            )
        )
    return drivers


def risk_badge(rec: Recommendation) -> str:
    """Low / Medium / High — how bumpy this stock looks (not a probability)."""
    m = rec.metrics
    points = 0
    price = rec.price or 0
    atr = m.atr
    if atr and price > 0:
        ann_vol = atr / price * (252 ** 0.5)
        if ann_vol >= 0.50:
            points += 2
        elif ann_vol >= 0.35:
            points += 1
    if m.near_52w_low:
        points += 1
    if m.debt_to_equity is not None and m.debt_to_equity > 150:
        points += 1
    if m.pe is not None and m.pe > 60:
        points += 1
    if points <= 1:
        return "Low"
    if points <= 3:
        return "Medium"
    return "High"


def portfolio_role(rec: Recommendation) -> str:
    """Suggested role for this stock inside a portfolio, in plain language."""
    if rec.action == Action.SELL:
        return "Avoid or reduce now"
    if rec.action == Action.HOLD:
        return "Watch — wait for a clearer signal"
    score = rec.score
    confident = (rec.confidence or 0.0) >= 0.6
    if score >= 50 and confident:
        return "Core holding"
    if score >= 30:
        return "Satellite pick"
    return "Small starter position"


def allocation_size(rec: Recommendation) -> float | None:
    """Suggested share of the equity sleeve (0..1). 0 / None = don't add yet."""
    if rec.action == Action.SELL or rec.action == Action.HOLD:
        return None
    if rec.score >= 50 and (rec.confidence or 0.0) >= 0.6:
        base = 0.10
    elif rec.score >= 30:
        base = 0.05
    else:
        base = 0.03
    risk_mult = {"Low": 1.0, "Medium": 0.8, "High": 0.5}.get(risk_badge(rec), 0.7)
    value = round(base * risk_mult, 2)
    return max(value, 0.02) if rec.action == Action.BUY else None


def what_could_go_wrong(rec: Recommendation) -> list[str]:
    """Plain-language risks specific to this stock."""
    m = rec.metrics
    risks: list[str] = []
    if m.pe is not None and m.pe > 60:
        risks.append(
            "The price already expects strong growth. If the company misses "
            "expectations, the stock can fall sharply."
        )
    if m.debt_to_equity is not None and m.debt_to_equity > 150:
        risks.append(
            "High debt means interest must be paid before shareholders get "
            "anything. A downturn or rising rates could hurt profits."
        )
    if m.near_52w_low:
        risks.append("The stock is near its 52-week low — the downtrend could continue.")
    if m.rsi is not None and m.rsi >= 70:
        risks.append("The stock recently became overbought, so a short-term pullback is possible.")
    if rec.pillars.get("trend", 0) < 0:
        risks.append("The longer-term trend is still down — patience needed.")
    risks.append(
        "No result is guaranteed. A broad market fall would probably lower this stock too."
    )
    return risks


def build_thesis(rec: Recommendation) -> Thesis:
    """Assemble the full plain-language thesis card for a recommendation."""
    drivers = build_drivers(rec.pillars, rec.reasons)
    badge = risk_badge(rec)
    role = portfolio_role(rec)
    allocation = allocation_size(rec)

    pos_drivers = [d for d in drivers if d.positive is True]
    neg_drivers = [d for d in drivers if d.positive is False]
    pos_names = " and ".join(d.label for d in pos_drivers[:2])
    neg_names = " and ".join(d.label for d in neg_drivers[:2])

    parts = [f"{rec.metrics.name or rec.symbol} looks {role.lower()}."]
    if pos_names:
        parts.append(f"{pos_names} are pointing the right way.")
    if neg_names:
        parts.append(f"{neg_names} are dragging it down.")
    if rec.confidence is not None:
        parts.append(
            f"The signals agree on a confidence level of {rec.confidence:.0%}."
        )
    parts.append(
        f"We'd size it at about {allocation:.0%} of your shares budget."
        if allocation
        else "We wouldn't add to it right now."
    )

    return Thesis(
        risk_badge=badge,
        portfolio_role=role,
        allocation_size=allocation,
        drivers=drivers,
        what_could_go_wrong=what_could_go_wrong(rec),
        thesis=" ".join(parts),
    )
