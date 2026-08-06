"""Goal-based plan generator tests (no network — stubbed analysis)."""
from screener.core.models import Action, Recommendation, RiskLevel, StockMetrics
from screener.services.plan_service import CANDIDATE_UNIVERSE, PlanService

SECTORS = ["Technology", "Banking", "Energy", "FMCG", "Auto"]


def _rec(symbol: str, score: float, sector: str) -> Recommendation:
    return Recommendation(
        symbol=f"{symbol}.NS",
        action=Action.BUY if score > 0 else Action.HOLD,
        score=score,
        price=100.0,
        reasons=["Price above 50-DMA (90.0) — short-term uptrend"],
        metrics=StockMetrics(name=f"{symbol} Ltd", sector=sector, pe=20, roe=0.2),
        confidence=0.6,
        pillars={"trend": 20, "momentum": 10, "volume": 0, "fundamentals": 5},
    )


class StubAnalysis:
    def __init__(self):
        self.scores = {
            "RELIANCE.NS": _rec("RELIANCE", 80, "Energy"),
            "TCS.NS": _rec("TCS", 70, "Technology"),
            "INFY.NS": _rec("INFY", 60, "Technology"),
            "HDFCBANK.NS": _rec("HDFCBANK", 50, "Banking"),
            "SBIN.NS": _rec("SBIN", 40, "Banking"),
            "ITC.NS": _rec("ITC", 30, "FMCG"),
            "LT.NS": _rec("LT", 20, "Construction"),
            "TATAMOTORS.NS": _rec("TATAMOTORS", 10, "Auto"),
        }
        self.calls = []

    def analyze(self, symbol: str, app_config=None):
        self.calls.append(symbol)
        key = f"{symbol}.NS"
        if key in self.scores:
            return self.scores[key]
        return Recommendation(
            symbol=f"{symbol}.NS",
            action=Action.HOLD,
            score=-20,
            price=100.0,
            error="insufficient price history",
        )


def _plan(analysis=None, **kwargs):
    service = PlanService(analysis_service=analysis or StubAnalysis())
    defaults = {"risk_level": "moderate", "monthly_amount": 10000, "horizon_years": 10, "goal": "wealth"}
    defaults.update(kwargs)
    return service.build_plan(**defaults)


def test_basket_is_size_three_to_five_and_buy_signals():
    plan = _plan()
    assert 3 <= len(plan.basket) <= 5
    for item in plan.basket:
        assert item.action == Action.BUY
        assert item.symbol
        assert item.plain
        assert item.weight > 0


def test_basket_is_sector_diversified():
    plan = _plan()
    sectors = [item.sector for item in plan.basket if item.sector]
    assert len(sectors) == len(set(sectors)), "same sector should not appear twice"


def test_weights_sum_to_one():
    plan = _plan()
    total = sum(item.weight for item in plan.basket)
    assert abs(total - 1.0) < 1e-3


def test_asset_split_follows_risk_level():
    plan = _plan(risk_level="aggressive")
    assert plan.asset_split["equity_delivery"] >= 0.5
    conservative = _plan(risk_level="conservative")
    assert conservative.asset_split["liquid"] >= 0.4


def test_return_ranges_are_ordered_and_labeled():
    plan = _plan(risk_level="moderate")
    assert plan.expected_return_range == [0.09, 0.12]
    assert plan.conservative_return_range[0] < plan.expected_return_range[0]


def test_tax_goal_adds_elss_fund():
    plan = _plan(goal="tax")
    assert any("ELSS" in fund for fund in plan.mutual_funds)


def test_notes_mention_quarterly_rebalancing():
    plan = _plan()
    assert any("quarter" in note.lower() for note in plan.notes)


def test_candidate_universe_is_sector_diverse_and_sized():
    assert 15 <= len(CANDIDATE_UNIVERSE) <= 25
    assert len(CANDIDATE_UNIVERSE) == len(set(CANDIDATE_UNIVERSE))


def test_plan_scans_only_the_curated_universe():
    analysis = StubAnalysis()
    _plan(analysis=analysis)
    scanned = {s.removesuffix(".NS") for s in analysis.calls}
    assert scanned <= set(CANDIDATE_UNIVERSE)


def test_horizon_and_amount_pass_through():
    plan = _plan(monthly_amount=25000, horizon_years=15)
    assert plan.monthly_amount == 25000
    assert plan.horizon_years == 15


def test_risk_level_accepts_string_or_enum():
    assert _plan(risk_level="aggressive").risk_level == RiskLevel.AGGRESSIVE
    assert _plan(risk_level=RiskLevel.MODERATE).risk_level == RiskLevel.MODERATE
