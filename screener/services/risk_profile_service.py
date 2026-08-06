"""Risk Profile Service — beginner onboarding questionnaire.

Turns 5 plain-language questions (no stock-market vocabulary needed) into a
Risk Profile (Conservative / Moderate / Aggressive) plus a suggested asset
split (equity delivery vs mutual funds vs liquid). Persisted per user.

The scoring is deliberately simple and transparent: each answer carries a few
points, they are summed, and the sum maps to a profile. The mapping is
published here so it can be reviewed and tuned by the product owner.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from screener.core.models import RiskLevel, RiskProfile
from screener.core.user_models import UserStore, user_store


# --------------------------------------------------------------------------- #
# Question bank (plain-language, beginner friendly)
# --------------------------------------------------------------------------- #

# Each option: {value, label, points}
QUESTIONS: list[dict[str, Any]] = [
    {
        "id": "goal",
        "question": "What is your main reason for investing?",
        "options": [
            {"value": "wealth", "label": "Build wealth over the long term", "points": 2},
            {"value": "retirement", "label": "Save for retirement / financial freedom", "points": 2},
            {"value": "tax", "label": "Save tax (like an ELSS fund)", "points": 1},
            {"value": "goal", "label": "A specific goal (education, a house)", "points": 0},
            {"value": "safe", "label": "Grow money safely in the short term", "points": -2},
        ],
    },
    {
        "id": "horizon",
        "question": "How long do you plan to keep this money invested?",
        "options": [
            {"value": "lt7", "label": "More than 7 years", "points": 2},
            {"value": "3to7", "label": "3 to 7 years", "points": 1},
            {"value": "1to3", "label": "1 to 3 years", "points": -1},
            {"value": "lt1", "label": "Less than a year", "points": -2},
        ],
    },
    {
        "id": "amount",
        "question": "About how much can you invest each month?",
        "options": [
            {"value": "gt1l", "label": "More than ₹1,00,000", "points": 0},
            {"value": "25kto1l", "label": "₹25,000 to ₹1,00,000", "points": 0},
            {"value": "5kto25k", "label": "₹5,000 to ₹25,000", "points": 0},
            {"value": "lt5k", "label": "Under ₹5,000", "points": 0},
        ],
    },
    {
        "id": "loss_tolerance",
        "question": "If your investment dropped 20% for a while, you would…",
        "options": [
            {"value": "ride", "label": "Be comfortable — I know markets go up and down", "points": 2},
            {"value": "stay", "label": "Be uneasy, but I'd hold on and wait", "points": 0},
            {"value": "sell", "label": "Probably sell to stop further losses", "points": -1},
            {"value": "cannot", "label": "Not be able to accept that at all", "points": -2},
        ],
    },
    {
        "id": "experience",
        "question": "How familiar are you with investing?",
        "options": [
            {"value": "regular", "label": "I invest regularly", "points": 1},
            {"value": "some", "label": "I've invested a little before", "points": 0},
            {"value": "new", "label": "This is my first time", "points": -1},
        ],
    },
]

_OPTIONS: dict[str, dict[str, int]] = {
    question["id"]: {option["value"]: option["points"] for option in question["options"]}
    for question in QUESTIONS
}

# --------------------------------------------------------------------------- #
# Profile definitions
# --------------------------------------------------------------------------- #

PROFILES: dict[RiskLevel, dict[str, Any]] = {
    RiskLevel.CONSERVATIVE: {
        "label": "Conservative",
        "summary": (
            "You prefer safety and steady growth. Your money stays mostly in "
            "safer options, with a smaller slice in shares."
        ),
        "asset_split": {"equity_delivery": 0.20, "mutual_funds": 0.40, "liquid": 0.40},
        "expected_return_range": [0.06, 0.09],
    },
    RiskLevel.MODERATE: {
        "label": "Moderate",
        "summary": (
            "You're happy to accept some ups and downs for better long-term "
            "growth. A balanced mix of shares and safer options suits you."
        ),
        "asset_split": {"equity_delivery": 0.40, "mutual_funds": 0.40, "liquid": 0.20},
        "expected_return_range": [0.09, 0.12],
    },
    RiskLevel.AGGRESSIVE: {
        "label": "Aggressive",
        "summary": (
            "You can ride out big swings and want maximum long-term growth. "
            "Most of your money goes into shares."
        ),
        "asset_split": {"equity_delivery": 0.60, "mutual_funds": 0.30, "liquid": 0.10},
        "expected_return_range": [0.12, 0.18],
    },
}

_LEVEL_BY_SCORE = (
    (RiskLevel.CONSERVATIVE, -2),
    (RiskLevel.MODERATE, 3),
    (RiskLevel.AGGRESSIVE, 10**9),
)

# Convenience views for other services (labels / asset splits / return ranges).
PROFILE_LABELS: dict[RiskLevel, str] = {
    level: PROFILES[level]["label"] for level in PROFILES
}
PROFILE_SPLITS: dict[RiskLevel, dict[str, float]] = {
    level: dict(PROFILES[level]["asset_split"]) for level in PROFILES
}
PROFILE_RETURNS: dict[RiskLevel, list[float]] = {
    level: list(PROFILES[level]["expected_return_range"]) for level in PROFILES
}


class RiskProfileService:
    """Compute, persist and retrieve a user's risk profile."""

    def __init__(self, store: UserStore | None = None):
        self._store = store or user_store

    # ------------------------------------------------------------------ #
    # Questions
    # ------------------------------------------------------------------ #

    def questions(self) -> list[dict[str, Any]]:
        """Return the question bank without exposing the points scoring."""
        return [
            {
                "id": q["id"],
                "question": q["question"],
                "options": [{"value": o["value"], "label": o["label"]} for o in q["options"]],
            }
            for q in QUESTIONS
        ]

    # ------------------------------------------------------------------ #
    # Scoring
    # ------------------------------------------------------------------ #

    def compute_profile(self, answers: dict[str, str]) -> RiskProfile:
        """Score a set of answers (question_id -> option value) into a profile."""
        score = 0
        normalized: dict[str, str] = {}
        for question_id, option_value in answers.items():
            if question_id not in _OPTIONS:
                continue
            points = _OPTIONS[question_id].get(option_value)
            if points is None:
                continue
            score += points
            normalized[question_id] = option_value

        level = RiskLevel.CONSERVATIVE
        for candidate, threshold in _LEVEL_BY_SCORE:
            if score <= threshold:
                level = candidate
                break

        return RiskProfile(
            level=level,
            label=PROFILES[level]["label"],
            summary=PROFILES[level]["summary"],
            asset_split=dict(PROFILES[level]["asset_split"]),
            expected_return_range=list(PROFILES[level]["expected_return_range"]),
            answers=normalized,
            created_at=datetime.now(),
        )

    # ------------------------------------------------------------------ #
    # Persistence (stored inside the user's preferences dict)
    # ------------------------------------------------------------------ #

    def save_profile(self, user_id: str, answers: dict[str, str]) -> RiskProfile:
        profile = self.compute_profile(answers)
        prefs = self._store.get_preferences(user_id)
        prefs["risk_profile"] = profile.model_dump(mode="json")
        self._store.update_preferences(user_id, prefs)
        return profile

    def get_profile(self, user_id: str) -> RiskProfile | None:
        prefs = self._store.get_preferences(user_id)
        raw = prefs.get("risk_profile")
        if not isinstance(raw, dict):
            return None
        try:
            return RiskProfile.model_validate(raw)
        except Exception:
            return None
