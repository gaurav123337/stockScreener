"""Tests for the Phase-1 trust layer: multi-horizon verification, auditable
logging of every action (including HOLD), the confidence/pillar fields, and
CSV round-tripping of the new columns.
"""
import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from screener.core.models import Action, PredictionRecord, Recommendation
from screener.infrastructure.persistence.csv_repository import CSVPredictionRepository
from screener.services.verification_service import VerificationService


class FakeProvider:
    """In-memory history provider for verification tests."""

    def __init__(self, frames: dict[str, pd.DataFrame]):
        self._frames = frames

    def fetch_history(self, symbol: str, period: str = "1y", interval: str = "1d"):
        return self._frames.get(symbol)


def _frame(prices, start="2024-01-01"):
    idx = pd.date_range(start, periods=len(prices), freq="B")
    return pd.DataFrame(
        {
            "Open": prices,
            "High": [p * 1.01 for p in prices],
            "Low": [p * 0.99 for p in prices],
            "Close": prices,
            "Volume": [1_000_000] * len(prices),
        },
        index=idx,
    )


def _rising_frame(n=900, base=100.0, step=0.002):
    return _frame([base * (1 + step * i) for i in range(n)])


def _make_service(tmp_path, records, provider_frames):
    repo = CSVPredictionRepository(tmp_path / "pred.csv")
    for r in records:
        repo.save(r)
    return VerificationService(
        repository=repo,
        data_provider=FakeProvider(provider_frames),
    )


# --------------------------------------------------------------------------- #
# Multi-horizon rolling verification
# --------------------------------------------------------------------------- #
def test_verify_evaluates_each_elapsed_horizon(tmp_path):
    today = datetime.now()
    t0 = today - timedelta(days=200)  # 30d + 90d elapsed, 365d not yet
    rising = _rising_frame()

    rec = PredictionRecord(
        ts=t0,
        symbol="RELIANCE",
        action=Action.BUY,
        price_at_call=100.0,
        horizon_days=365,
        score=40.0,
        confidence=0.6,
        user_id="u1",
    )
    # Benchmark is the same steady uptrend so a rising BUY always beats it.
    provider = {"RELIANCE": rising, "^NSEI": _rising_frame(base=50.0, step=0.001)}
    service = _make_service(tmp_path, [rec], provider)

    report = service.verify()

    assert report.evaluated_now == 1
    assert report.total_evaluated == 1
    assert len(report.horizons) == 3

    by_h = {h.horizon_days: h for h in report.horizons}
    assert by_h[30].n == 1
    assert by_h[30].hit_rate == 100.0
    assert by_h[30].avg_return and by_h[30].avg_return > 0
    assert by_h[30].benchmark_avg_return is not None
    assert by_h[30].vs_benchmark is not None
    assert by_h[30].max_drawdown is not None
    assert by_h[30].by_action["BUY"]["n"] == 1

    assert by_h[90].n == 1
    assert by_h[365].n == 0  # horizon still open -> rolling window excludes it
    assert report.window_start is not None
    assert report.generated_at is not None


def test_verify_sell_and_hold_semantics(tmp_path):
    today = datetime.now()
    t0 = today - timedelta(days=40)
    # Falling series: a SELL is right, a HOLD is wrong (moved >2%).
    falling = _frame([100.0 * (1 - 0.01 * i) for i in range(200)])

    records = [
        PredictionRecord(
            ts=t0, symbol="SELLSTK", action=Action.SELL,
            price_at_call=100.0, horizon_days=365,
        ),
        PredictionRecord(
            ts=t0, symbol="HOLDSTK", action=Action.HOLD,
            price_at_call=100.0, horizon_days=365,
        ),
    ]
    provider = {"SELLSTK": falling, "HOLDSTK": falling, "^NSEI": falling}
    service = _make_service(tmp_path, records, provider)

    report = service.verify()
    by_h = {h.horizon_days: h for h in report.horizons}
    assert by_h[30].n == 2
    # SELL won (price fell), HOLD lost (moved well past the flat band).
    assert by_h[30].by_action["SELL"]["n"] == 1
    assert by_h[30].by_action["SELL"]["hit_rate"] == 100.0
    assert by_h[30].by_action["HOLD"]["n"] == 1
    assert by_h[30].by_action["HOLD"]["hit_rate"] == 0.0


# --------------------------------------------------------------------------- #
# Auditable logging: all actions persist with score/confidence/user_id
# --------------------------------------------------------------------------- #
def test_log_prediction_persists_hold_and_new_fields(tmp_path):
    repo = CSVPredictionRepository(tmp_path / "pred.csv")
    service = VerificationService(
        repository=repo,
        data_provider=FakeProvider({}),
    )

    rec = Recommendation(
        symbol="TATA.NS",
        action=Action.HOLD,
        score=5.0,
        price=100.0,
        confidence=0.55,
        pillars={"trend": 1.0, "momentum": 0.5, "volume": 0.0, "fundamentals": 0.5},
    )
    service.log_prediction(rec, user_id="u9")

    rows = repo.get_all()
    assert len(rows) == 1
    assert rows[0].action == Action.HOLD
    assert rows[0].score == 5.0
    assert rows[0].confidence == 0.55
    assert rows[0].user_id == "u9"
    assert rows[0].price_at_call == 100.0
    assert rows[0].ts.tzinfo is None


def test_csv_roundtrip_preserves_zero_score(tmp_path):
    repo = CSVPredictionRepository(tmp_path / "pred.csv")
    rec = PredictionRecord(
        ts=datetime.now(),
        symbol="ZERO.NS",
        action=Action.BUY,
        price_at_call=50.0,
        score=0.0,
        confidence=0.0,
        user_id="u0",
    )
    repo.save(rec)
    (loaded,) = repo.get_all()
    assert loaded.score == 0.0
    assert loaded.confidence == 0.0
    assert loaded.user_id == "u0"


def test_log_prediction_skips_errors_and_missing_price(tmp_path):
    repo = CSVPredictionRepository(tmp_path / "pred.csv")
    service = VerificationService(repository=repo, data_provider=FakeProvider({}))
    service.log_prediction(
        Recommendation(symbol="ERR.NS", action=Action.BUY, score=1.0, price=0.0, error="insufficient price history")
    )
    assert repo.get_all() == []


def test_log_recommendations_never_raises(tmp_path):
    repo = CSVPredictionRepository(tmp_path / "pred.csv")
    service = VerificationService(repository=repo, data_provider=FakeProvider({}))
    service.log_recommendations(
        [
            Recommendation(symbol="OK.NS", action=Action.BUY, score=1.0, price=10.0),
            Recommendation(symbol="BAD.NS", action=Action.BUY, score=1.0, price=0.0, error="boom"),
        ],
        user_id="u2",
    )
    assert len(repo.get_all()) == 1


# --------------------------------------------------------------------------- #
# Backfill seed: /api/verify shows dated, nonzero results from day one
# --------------------------------------------------------------------------- #
def _replay_record(ts, symbol="RELIANCE", action=Action.BUY, price=100.0):
    return PredictionRecord(
        ts=ts, symbol=symbol, action=action,
        price_at_call=price, horizon_days=365,
        score=40.0, confidence=0.6,
    )


def test_seed_from_backtest_stamps_and_dedupes(tmp_path):
    repo = CSVPredictionRepository(tmp_path / "pred.csv")
    service = VerificationService(repository=repo, data_provider=FakeProvider({}))

    t0 = datetime.now() - timedelta(days=200)
    records = [_replay_record(t0), _replay_record(t0 + timedelta(days=21))]

    added = service.seed_from_backtest(records)
    assert added == 2
    rows = repo.get_all()
    assert all(r.user_id == "system/backtest" for r in rows)

    # Same payload re-seeded (e.g. restart) adds nothing.
    assert service.seed_from_backtest(records) == 0
    assert len(repo.get_all()) == 2
    assert service.has_backtest_seed() is True


def test_seeded_signals_drive_nonzero_verify_results(tmp_path):
    today = datetime.now()
    rising = _rising_frame()

    service = VerificationService(
        repository=CSVPredictionRepository(tmp_path / "pred.csv"),
        data_provider=FakeProvider({"RELIANCE": rising, "^NSEI": _rising_frame(base=50.0, step=0.001)}),
    )
    # Seed 3 replayed BUY signals all >= 30 days old on a rising stock.
    records = [
        _replay_record(today - timedelta(days=120), symbol="RELIANCE"),
        _replay_record(today - timedelta(days=100), symbol="RELIANCE"),
        _replay_record(today - timedelta(days=60), symbol="RELIANCE"),
    ]
    service.seed_from_backtest(records)

    report = service.verify()
    assert report.total_evaluated == 3
    assert report.overall_hit_rate == 100.0
    by_h = {h.horizon_days: h for h in report.horizons}
    assert by_h[30].n == 3
    assert by_h[30].hit_rate == 100.0
    assert report.window_start is not None


def test_repository_migrates_stale_header(tmp_path):
    """A predictions.csv written before score/confidence/user_id were added must
    be upgraded so new fields are readable and backfilled rows stay deduped."""
    pred = tmp_path / "pred.csv"
    old_header = [
        "ts", "symbol", "action", "price_at_call", "target", "stop_loss",
        "horizon_days", "evaluated", "eval_date", "price_at_eval",
        "outcome", "return_pct",
    ]
    with pred.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(old_header)
        w.writerow(["2026-01-01T00:00:00", "RELIANCE", "BUY", "100", "", "", "30",
                    "0", "", "", "", "", "40", "0.6", "system/backtest"])
        w.writerow(["2026-01-01T00:00:00", "RELIANCE", "BUY", "100", "", "", "30",
                    "0", "", "", "", "", "40", "0.6", "system/backtest"])
        w.writerow(["2026-01-01T00:00:00", "TATA.NS", "HOLD", "50", "", "", "30",
                    "0", "", "", "", "", "5", "0.5", "guest"])

    repo = CSVPredictionRepository(pred)
    rows = repo.get_all()
    backtest = [r for r in rows if r.user_id == "system/backtest"]
    # Header migrated AND duplicates dropped.
    assert len(backtest) == 1
    assert backtest[0].score == 40.0
    assert backtest[0].confidence == 0.6
    assert any(r.user_id == "guest" for r in rows)
