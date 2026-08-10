"""Offline tests for the Phase-5 feedback loop and check-before-buy services.

Prediction records and recommendations are constructed directly (no network).
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from screener.core.models import (
    Action,
    Outcome,
    PredictionRecord,
    Recommendation,
    StockMetrics,
    Thesis,
)
from screener.core.responses import NotFoundError, ValidationError
from screener.core.subscription_models import SubscriptionStore
from screener.core.user_models import UserProfile
from screener.services.check_before_buy_service import CheckBeforeBuyService
from screener.services.feedback_loop_service import FeedbackLoopService


def make_user() -> UserProfile:
    return UserProfile(
        user_id="u1",
        username="u1",
        role="pro",
        created_at=datetime.now(timezone.utc),
    )


class FakeRepo:
    def __init__(self, records):
        self._records = records

    def get_all(self):
        return list(self._records)


def _record(score: float, outcome: Outcome, action: Action = Action.BUY,
            ret: float = 0.0) -> PredictionRecord:
    ts = datetime.now(timezone.utc) - timedelta(days=60)
    return PredictionRecord(
        ts=ts,
        symbol="RELIANCE",
        action=action,
        price_at_call=100.0,
        target=110.0,
        stop_loss=95.0,
        horizon_days=30,
        evaluated=True,
        eval_date=ts + timedelta(days=30),
        price_at_eval=105.0,
        outcome=outcome,
        return_pct=ret,
        score=score,
        user_id="u1",
    )


# ------------------------------------------------------------- feedback loop --

class FeedbackLoopTests(unittest.TestCase):
    def test_outcome_stats_bands(self):
        recs = [
            _record(45.0, Outcome.CORRECT, ret=0.08),   # high win
            _record(40.0, Outcome.TARGET_HIT, ret=0.1), # high win
            _record(35.0, Outcome.WRONG, ret=-0.05),    # high loss
            _record(38.0, Outcome.CORRECT, ret=0.05),   # high win
            _record(42.0, Outcome.TARGET_HIT, ret=0.09),# high win
            _record(33.0, Outcome.WRONG, ret=-0.04),    # high loss
            _record(5.0, Outcome.CORRECT, ret=0.03),    # mid win
            _record(-25.0, Outcome.WRONG, ret=-0.06),   # low loss
            _record(-30.0, Outcome.STOP_HIT, ret=-0.05),# low loss
            _record(-32.0, Outcome.STOP_HIT, ret=-0.04),# low loss
            _record(-28.0, Outcome.WRONG, ret=-0.07),   # low loss
            _record(-35.0, Outcome.CORRECT, ret=0.01),  # low win
            _record(-40.0, Outcome.WRONG, ret=-0.08),   # low loss
        ]
        svc = FeedbackLoopService(repo=FakeRepo(recs))
        stats = svc.outcome_stats()
        self.assertEqual(stats["evaluated"], 13)
        self.assertAlmostEqual(stats["overall_hit_rate"], 6 / 13, places=3)
        self.assertEqual(stats["by_score_band"]["high"]["n"], 6)
        self.assertEqual(stats["by_score_band"]["low"]["n"], 6)
        self.assertIsNotNone(stats["score_predictiveness"])
        self.assertGreater(stats["score_predictiveness"], 0)

    def test_insufficient_data_no_suggestions(self):
        recs = [_record(40.0, Outcome.CORRECT), _record(-30.0, Outcome.WRONG)]
        svc = FeedbackLoopService(repo=FakeRepo(recs))
        res = svc.weight_suggestions()
        self.assertFalse(res["sufficient_data"])
        self.assertEqual(res["suggestions"], [])

    def test_changelog_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SubscriptionStore(Path(tmp) / "subs.db")
            svc = FeedbackLoopService(repo=FakeRepo([]), store=store)
            entry = svc.publish_change(
                make_user(),
                {
                    "version": "1.1.0",
                    "title": "Rebalance trend weight",
                    "summary": "trend was overweight",
                    "weight_changes": {"trend": {"old": 45.0, "new": 40.0}},
                },
            )
            self.assertTrue(entry.entry_id)
            entries = svc.changelog()
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["weight_changes"]["trend"]["new"], 40.0)


# ---------------------------------------------------------- check-before-buy --

class CheckBeforeBuyTests(unittest.TestCase):
    def _rec(self) -> Recommendation:
        return Recommendation(
            symbol="RELIANCE",
            action=Action.BUY,
            score=42.0,
            price=3000.0,
            entry=2950.0,
            target=3600.0,
            stop_loss=2750.0,
            risk_reward=3.0,
            reasons=["trend up"],
            metrics=StockMetrics(pe=28.0, sector="Oil & Gas"),
            thesis_data=Thesis(risk_badge="Medium", allocation_size=0.1),
        )

    def test_checklist_has_all_sections(self):
        svc = CheckBeforeBuyService()
        result = svc.checklist(make_user(), self._rec())
        titles = [i["title"] for i in result["items"]]
        self.assertIn("Price vs entry", titles)
        self.assertIn("Upside to target", titles)
        self.assertIn("Stop-loss distance", titles)
        self.assertIn("Valuation (P/E)", titles)
        self.assertIn("Position size", titles)
        self.assertIn("Compliance & role", titles)
        self.assertEqual(result["symbol"], "RELIANCE")
        self.assertIn("brokers", result)
        self.assertIn("disclaimer", result)

    def test_rejects_failed_recommendation(self):
        svc = CheckBeforeBuyService()
        rec = self._rec()
        rec.error = "no data"
        with self.assertRaises(ValidationError):
            svc.checklist(make_user(), rec)

    def test_broker_deep_links_interpolate_symbol(self):
        svc = CheckBeforeBuyService()
        link = svc.broker_deep_link("groww", "reliance")
        self.assertIn("RELIANCE", link["web"])
        self.assertIn("RELIANCE", link["app"])

    def test_broker_deep_link_unknown_broker(self):
        svc = CheckBeforeBuyService()
        with self.assertRaises(NotFoundError):
            svc.broker_deep_link("notabroker", "RELIANCE")

    def test_broker_deep_link_requires_symbol(self):
        svc = CheckBeforeBuyService()
        with self.assertRaises(ValidationError):
            svc.broker_deep_link("groww", "   ")

    def test_broker_list_is_review_only(self):
        svc = CheckBeforeBuyService()
        brokers = svc.brokers()
        self.assertTrue(len(brokers) >= 3)
        ids = {b["id"] for b in brokers}
        self.assertIn("zerodha_kite", ids)
