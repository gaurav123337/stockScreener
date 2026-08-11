"""Tests for the Phase-5 trust & retention layer: explainer content moat
(ContentService), monthly scorecard + illustrative success stories
(ScorecardService). The scorecard tests inject fakes so they stay offline.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from screener.services.content_service import ContentService
from screener.services.scorecard_service import ScorecardService

from screener.core.models import BacktestReport, HorizonStats, VerificationReport


def _sample_backtest() -> BacktestReport:
    return BacktestReport(
        status="ok",
        generated_at=datetime.now(timezone.utc),
        window_start=datetime(2024, 1, 1),
        window_end=datetime(2026, 8, 1),
        universe=["RELIANCE", "TCS"],
        universe_size=2,
        universe_coverage=0.0,
        horizons=[
            HorizonStats(
                horizon_days=30,
                n=120,
                hit_rate=0.58,
                avg_return=0.012,
                benchmark_avg_return=0.008,
                vs_benchmark=0.004,
                max_drawdown=-0.18,
            )
        ],
        methodology=["no lookahead", "equal-weight"],
        notes=["caveat"],
    )


def _sample_verification() -> VerificationReport:
    return VerificationReport(
        evaluated_now=10,
        total_evaluated=8,
        overall_hit_rate=0.6,
        benchmark_symbol="^NSEI",
        generated_at=datetime.now(timezone.utc),
    )


class FakeBacktestService:
    def get(self):
        return _sample_backtest()


class FakeVerificationService:
    def verify(self):
        return _sample_verification()


# ------------------------------------------------------------------ content --


def test_content_list_exposes_expected_catalogue():
    svc = ContentService()
    articles = svc.list_articles()
    slugs = {a["slug"] for a in articles}
    assert {
        "what-is-pe-ratio",
        "index-fund-vs-etf",
        "elss-tax-saving",
        "signal-score-explained",
        "drawdowns-and-staying-invested",
    } <= slugs
    for a in articles:
        assert a["title"]
        assert a["excerpt"]
        assert a["category"]
        assert a["reading_minutes"] > 0


def test_content_get_by_slug_returns_sections():
    svc = ContentService()
    article = svc.get_article("what-is-pe-ratio")
    assert article.slug == "what-is-pe-ratio"
    assert article.sections
    assert any(s.bullets for s in article.sections)
    assert article.word_count > 100


def test_content_unknown_slug_raises():
    import pytest
    from screener.core.responses import NotFoundError

    svc = ContentService()
    with pytest.raises(NotFoundError):
        svc.get_article("does-not-exist")


def test_content_search_matches_titles_and_bodies():
    svc = ContentService()
    hits = svc.search("P/E")
    assert any(h["slug"] == "what-is-pe-ratio" for h in hits)


# --------------------------------------------------------------- scorecard --


def test_monthly_scorecard_uses_injected_fakes(tmp_path):
    svc = ScorecardService(
        backtest_service=FakeBacktestService(),
        verification_service=FakeVerificationService(),
        cache_file=str(tmp_path / "scorecard_test.json"),
    )
    scorecard = svc.refresh()
    assert scorecard["period"] == datetime.now(timezone.utc).strftime("%Y-%m")
    assert scorecard["universe_size"] == 2
    assert scorecard["universe_coverage"] == 0.0
    assert scorecard["horizons"][0]["horizon_days"] == 30
    assert scorecard["live_evaluated"] == 8
    assert scorecard["live_overall_hit_rate"] == 0.6
    assert scorecard["benchmark_symbol"] == "^NSEI"
    assert "disclaimer" in scorecard


def test_fast_path_skips_verification(tmp_path):
    calls = {"backtest": 0, "verify": 0}

    class CountingBacktest(FakeBacktestService):
        def get(self):
            calls["backtest"] += 1
            return _sample_backtest()

    class CountingVerify(FakeVerificationService):
        def verify(self):
            calls["verify"] += 1
            return _sample_verification()

    svc = ScorecardService(
        backtest_service=CountingBacktest(),
        verification_service=CountingVerify(),
        cache_file=str(tmp_path / "scorecard_fast_test.json"),
    )
    svc.monthly_scorecard()
    assert calls["verify"] == 0  # fast path never touches the network
    scorecard = svc.monthly_scorecard()
    assert scorecard["live_overall_hit_rate"] is None  # cached fast snapshot
    svc.refresh()
    assert calls["verify"] == 1  # explicit refresh runs the full pass


def test_monthly_scorecard_is_cached_same_period(tmp_path):
    calls = {"backtest": 0, "verify": 0}

    class CountingBacktest(FakeBacktestService):
        def get(self):
            calls["backtest"] += 1
            return _sample_backtest()

    class CountingVerify(FakeVerificationService):
        def verify(self):
            calls["verify"] += 1
            return _sample_verification()

    svc = ScorecardService(
        backtest_service=CountingBacktest(),
        verification_service=CountingVerify(),
        cache_file=str(tmp_path / "scorecard_cache_test.json"),
    )
    svc.monthly_scorecard()
    svc.monthly_scorecard()
    assert calls["backtest"] == 1
    assert calls["verify"] == 0


def test_scorecard_tolerates_verification_failure(tmp_path):
    class BrokenVerify(FakeVerificationService):
        def verify(self):
            raise RuntimeError("network down")

    svc = ScorecardService(
        backtest_service=FakeBacktestService(),
        verification_service=BrokenVerify(),
        cache_file=str(tmp_path / "scorecard_fail_test.json"),
    )
    scorecard = svc.refresh()  # full path must still survive a verify failure
    assert scorecard["live_overall_hit_rate"] is None
    assert scorecard["horizons"]


def test_success_stories_are_labeled_illustrative():
    svc = ScorecardService()
    for story in svc.success_stories():
        assert story["illustrative"] is True
        assert story["title"]
        assert story["lesson"]
