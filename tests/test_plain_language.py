"""Plain-language glossary + thesis-card enrichment tests."""
from screener.core.models import Action, Recommendation, StockMetrics
from screener.services.plain_language import (
    build_drivers,
    build_thesis,
    glossary,
    risk_badge,
)

GOOD = Recommendation(
    symbol="TCS.NS",
    action=Action.BUY,
    score=62,
    price=3800,
    reasons=[
        "Price above 50-DMA (3600.0) — short-term uptrend",
        "Price above 200-DMA (3500.0) — long-term uptrend",
        "Golden-cross alignment (50-DMA > 200-DMA)",
        "RSI 62 — healthy bullish momentum",
        "ROE 32% — quality business",
        "PEG 0.9 < 1 — undervalued vs growth",
    ],
    metrics=StockMetrics(
        name="Tata Consultancy Services",
        sector="Technology",
        pe=31,
        roe=0.32,
        peg=0.9,
        rsi=62,
        atr=45,
    ),
    confidence=0.72,
    pillars={"trend": 45, "momentum": 15, "volume": 0, "fundamentals": 16},
)


def test_glossary_covers_key_metrics():
    terms = glossary()
    for key in ("pe", "roe", "rsi", "sma50", "stop_loss", "confidence", "score", "weight"):
        assert key in terms
        assert terms[key]["term"]
        assert terms[key]["plain"]


def test_drivers_are_four_plain_language_buckets():
    drivers = build_drivers(GOOD.pillars, GOOD.reasons)
    assert [d.key for d in drivers] == ["trend", "momentum", "value", "quality"]
    for driver in drivers:
        assert driver.label
        assert driver.plain
        assert not driver.why or any(w for w in driver.why)


def test_driver_bucketing_splits_fundamentals():
    drivers = build_drivers(GOOD.pillars, GOOD.reasons)
    by_key = {d.key: d for d in drivers}
    assert by_key["value"].positive is True
    assert by_key["quality"].positive is True
    # Fundamental pillar (16) split across value + quality reasons.
    assert by_key["value"].score + by_key["quality"].score == 16.0


def test_risk_badge():
    assert risk_badge(GOOD) == "Low"


def test_high_risk_stock_gets_high_badge():
    risky = GOOD.model_copy(
        update={
            "metrics": StockMetrics(
                pe=120, debt_to_equity=300, near_52w_low=True, atr=200, price=1000
            )
        }
    )
    assert risk_badge(risky) == "High"


def test_portfolio_role_and_allocation():
    thesis = build_thesis(GOOD)
    assert thesis.portfolio_role == "Core holding"
    assert thesis.allocation_size == 0.10


def test_hold_gets_no_allocation():
    hold = GOOD.model_copy(update={"action": Action.HOLD, "score": 5})
    thesis = build_thesis(hold)
    assert thesis.allocation_size is None
    assert "wait" in thesis.portfolio_role.lower()


def test_sell_gets_avoid_role():
    sell = GOOD.model_copy(update={"action": Action.SELL, "score": -60})
    thesis = build_thesis(sell)
    assert "avoid" in thesis.portfolio_role.lower()


def test_thesis_mentions_name_and_confidence():
    thesis = build_thesis(GOOD)
    assert "Tata Consultancy Services" in thesis.thesis
    assert "72%" in thesis.thesis
    assert len(thesis.what_could_go_wrong) >= 1


def test_wgw_mentions_specific_risks():
    rich = GOOD.model_copy(
        update={
            "metrics": StockMetrics(pe=80, debt_to_equity=250, rsi=75),
        }
    )
    risks = build_thesis(rich).what_could_go_wrong
    joined = " ".join(risks)
    assert "growth" in joined or "misses expectations" in joined
    assert "debt" in joined
    assert "overbought" in joined
