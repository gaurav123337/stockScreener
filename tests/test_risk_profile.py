"""Risk profile + onboarding tests."""
import pytest

from screener.core.models import RiskLevel
from screener.services.risk_profile_service import (
    QUESTIONS,
    RiskProfileService,
)

svc = RiskProfileService()


def test_question_bank_is_plain_language():
    qs = svc.questions()
    assert len(qs) == 5
    ids = [q["id"] for q in qs]
    assert ids == ["goal", "horizon", "amount", "loss_tolerance", "experience"]
    for q in qs:
        assert q["question"]
        assert len(q["options"]) >= 3
        for option in q["options"]:
            assert "points" not in option  # scoring is hidden from the UI


def test_aggressive_answers_map_to_aggressive():
    profile = svc.compute_profile(
        {
            "goal": "wealth",
            "horizon": "lt7",
            "amount": "5kto25k",
            "loss_tolerance": "ride",
            "experience": "regular",
        }
    )
    assert profile.level == RiskLevel.AGGRESSIVE
    assert profile.asset_split["equity_delivery"] >= 0.5
    assert profile.expected_return_range == [0.12, 0.18]


def test_conservative_answers_map_to_conservative():
    profile = svc.compute_profile(
        {
            "goal": "safe",
            "horizon": "lt1",
            "amount": "lt5k",
            "loss_tolerance": "cannot",
            "experience": "new",
        }
    )
    assert profile.level == RiskLevel.CONSERVATIVE
    assert profile.asset_split["liquid"] >= 0.4


def test_unknown_answers_are_ignored_without_crashing():
    profile = svc.compute_profile({"goal": "not-an-option", "horizon": "lt7"})
    assert profile.level in {RiskLevel.CONSERVATIVE, RiskLevel.MODERATE, RiskLevel.AGGRESSIVE}


def test_profile_persists_and_round_trips(monkeypatch):
    from screener.core.user_models import user_store

    store = user_store
    answers = {"goal": "tax", "horizon": "3to7", "amount": "25kto1l", "loss_tolerance": "stay", "experience": "some"}

    class FakeStore:
        def __init__(self):
            self.prefs: dict[str, dict] = {}

        def get_preferences(self, user_id: str):
            return self.prefs.get(user_id, {})

        def update_preferences(self, user_id: str, prefs: dict):
            self.prefs[user_id] = prefs

    service = RiskProfileService(store=FakeStore())
    saved = service.save_profile("u1", answers)
    loaded = service.get_profile("u1")
    assert loaded is not None
    assert loaded.level == saved.level
    assert loaded.answers == answers


def test_missing_profile_returns_none(monkeypatch):
    class EmptyStore:
        def get_preferences(self, user_id: str):
            return {}

        def update_preferences(self, user_id: str, prefs: dict):
            pass

    assert RiskProfileService(store=EmptyStore()).get_profile("nobody") is None


def test_all_levels_reachable():
    """The point range must be able to produce every profile level."""
    levels = set()
    for answers in [
        {"goal": "wealth", "horizon": "lt7", "loss_tolerance": "ride", "experience": "regular"},
        {"goal": "goal", "horizon": "1to3", "loss_tolerance": "stay", "experience": "some"},
        {"goal": "safe", "horizon": "lt1", "loss_tolerance": "cannot", "experience": "new"},
    ]:
        levels.add(svc.compute_profile(answers).level)
    assert levels == set(RiskLevel)
