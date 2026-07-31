"""Centralized configuration management using Pydantic Settings.

All application settings in one place, environment-variable aware,
and type-validated. No more scattered hardcoded values.

User overrides made via the dashboard are persisted to
``data/user_config.json`` and re-applied on startup.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DataConfig(BaseSettings):
    """Data fetching configuration."""
    model_config = SettingsConfigDict(env_prefix="SCREENER_DATA_")

    default_period: str = "1y"
    default_interval: str = "1d"
    retry_attempts: int = 2
    retry_pause_seconds: float = 1.0
    max_workers: int = 8


class ScoringConfig(BaseSettings):
    """Scoring engine thresholds."""
    model_config = SettingsConfigDict(env_prefix="SCREENER_SCORE_")

    buy_threshold: float = 30.0
    sell_threshold: float = -30.0
    trend_weight_sma50: float = 15.0
    trend_weight_sma200: float = 20.0
    trend_weight_cross: float = 10.0
    momentum_weight_rsi: float = 10.0
    momentum_weight_macd: float = 10.0
    momentum_weight_crossover: float = 5.0
    volume_weight: float = 5.0
    fundamental_peg_weight: float = 12.0
    fundamental_roe_weight: float = 8.0
    fundamental_debt_weight: float = 4.0


class RiskConfig(BaseSettings):
    """Risk management / trade levels."""
    model_config = SettingsConfigDict(env_prefix="SCREENER_RISK_")

    atr_multiplier: float = 1.5
    risk_reward_target: float = 2.0
    sma50_stop_discount: float = 0.98  # 2% below SMA50


class KnowledgeConfig(BaseSettings):
    """Knowledge base ingestion."""
    model_config = SettingsConfigDict(env_prefix="SCREENER_KB_")

    max_rules_per_doc: int = 12
    min_rule_length: int = 30
    max_rule_length: int = 220
    allowed_extensions: frozenset[str] = frozenset({".pdf", ".md", ".txt", ".srt", ".vtt"})


class VerificationConfig(BaseSettings):
    """Prediction verification."""
    model_config = SettingsConfigDict(env_prefix="SCREENER_VERIFY_")

    horizon_days: int = 30


class IndianApiConfig(BaseSettings):
    """Deployment-managed settings for the optional Indian market API."""
    model_config = SettingsConfigDict(env_prefix="SCREENER_INDIAN_API_")

    enabled: bool = False
    base_url: str = ""
    api_key: str = Field(default="", repr=False)
    auth_header: str = "X-Api-Key"
    auth_scheme: str = ""
    timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    retry_attempts: int = Field(default=2, ge=0, le=5)
    cache_ttl_seconds: int = Field(default=30, ge=0, le=3600)
    rate_limit_per_minute: int = Field(default=60, ge=1, le=10_000)

    @field_validator("auth_header")
    @classmethod
    def _validate_auth_header(cls, value: str) -> str:
        value = value.strip()
        if not value or any(char in value for char in "\r\n:"):
            raise ValueError("auth_header must be a valid HTTP header name")
        return value


class AppConfig(BaseSettings):
    """Root application configuration."""
    model_config = SettingsConfigDict(env_prefix="SCREENER_")

    # Paths
    root_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent)
    data_dir: Path | None = None
    knowledge_dir: Path | None = None
    knowledge_graph_dir: Path | None = None
    web_dir: Path | None = None

    # Sub-configs
    data: DataConfig = Field(default_factory=DataConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    knowledge: KnowledgeConfig = Field(default_factory=KnowledgeConfig)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)
    indian_api: IndianApiConfig = Field(default_factory=IndianApiConfig)
    market_data_provider: Literal["yahoo", "indian_api", "hybrid"] = "yahoo"

    # Environment
    environment: Literal["development", "production", "testing"] = "development"
    debug: bool = False

    # Default symbol universe
    default_universe: list[str] = Field(default_factory=lambda: [
        "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
        "BAJAJ-AUTO", "BAJAJFINSV", "BAJFINANCE", "BEL", "BHARTIARTL",
        "BPCL", "BRITANNIA", "CIPLA", "COALINDIA", "DRREDDY",
        "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE",
        "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK", "INDUSINDBK",
        "INFY", "ITC", "JSWSTEEL", "KOTAKBANK", "LT",
        "M&M", "MARUTI", "NESTLEIND", "NTPC", "ONGC",
        "POWERGRID", "RELIANCE", "SBILIFE", "SBIN", "SHRIRAMFIN",
        "SUNPHARMA", "TATACONSUM", "TATAMOTORS", "TATASTEEL", "TCS",
        "TECHM", "TITAN", "TRENT", "ULTRACEMCO", "WIPRO",
    ])

    @field_validator("data_dir", mode="before")
    @classmethod
    def _default_data_dir(cls, v, info):
        if v is None:
            return info.data["root_dir"] / "data"
        return Path(v)

    @field_validator("knowledge_dir", mode="before")
    @classmethod
    def _default_knowledge_dir(cls, v, info):
        if v is None:
            return info.data["root_dir"] / "knowledge"
        return Path(v)

    @field_validator("knowledge_graph_dir", mode="before")
    @classmethod
    def _default_knowledge_graph_dir(cls, v, info):
        if v is None:
            return info.data["root_dir"] / "knowledge_graph"
        return Path(v)

    @field_validator("web_dir", mode="before")
    @classmethod
    def _default_web_dir(cls, v, info):
        if v is None:
            return info.data["root_dir"] / "web"
        return Path(v)

    @property
    def predictions_file(self) -> Path:
        return self.data_dir / "predictions.csv"

    @property
    def broker_settings_file(self) -> Path:
        return self.data_dir / "broker_settings.json"

    @property
    def kb_file(self) -> Path:
        return self.knowledge_graph_dir / "market_knowledge.md"

    @property
    def learn_manifest_file(self) -> Path:
        return self.knowledge_graph_dir / ".learn_manifest.json"

    @property
    def user_config_file(self) -> Path:
        return self.data_dir / "user_config.json"

    def ensure_directories(self) -> None:
        """Create all required directories if they don't exist."""
        for d in (self.data_dir, self.knowledge_dir, self.knowledge_graph_dir):
            d.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Dashboard-editable settings (get / update / reset)
    # ------------------------------------------------------------------ #
    _SECTIONS = ("data", "scoring", "risk", "knowledge", "verification")

    @classmethod
    def _defaults(cls) -> dict[str, Any]:
        """Fresh-out-of-the-box defaults (no env vars, no user overrides)."""
        return cls().editable_snapshot()

    def editable_snapshot(self) -> dict[str, Any]:
        """Current values of every dashboard-editable setting."""
        snap: dict[str, Any] = {
            section: getattr(self, section).model_dump() for section in self._SECTIONS
        }
        # frozenset isn't JSON-friendly
        snap["knowledge"]["allowed_extensions"] = sorted(
            snap["knowledge"]["allowed_extensions"]
        )
        snap["default_universe"] = list(self.default_universe)
        return snap

    def load_user_overrides(self) -> None:
        """Re-apply persisted dashboard overrides (called at startup)."""
        try:
            if self.user_config_file.exists():
                saved = json.loads(self.user_config_file.read_text(encoding="utf-8"))
                if isinstance(saved, dict) and saved:
                    self._apply(saved)
        except Exception:
            pass  # corrupt file -> keep booting with defaults

    def update_settings(self, patch: dict[str, Any]) -> dict[str, Any]:
        """Validate & apply a partial settings patch, then persist it.

        Raises ValueError on unknown keys or invalid values.
        """
        if not isinstance(patch, dict) or not patch:
            raise ValueError("empty settings payload")

        allowed = self.editable_snapshot()
        unknown = [k for k in patch if k not in allowed]
        if unknown:
            raise ValueError(f"unknown setting(s): {', '.join(sorted(unknown))}")

        candidate = copy.deepcopy(allowed)
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(candidate.get(key), dict):
                bad = [k for k in value if k not in candidate[key]]
                if bad:
                    raise ValueError(
                        f"unknown {key} field(s): {', '.join(sorted(bad))}"
                    )
                candidate[key].update(value)
            else:
                candidate[key] = value

        # Type-validate by rebuilding the sub-configs
        validated: dict[str, Any] = {"default_universe": candidate["default_universe"]}
        for section in self._SECTIONS:
            model = type(getattr(self, section))
            validated[section] = model(**candidate[section]).model_dump()

        self._apply(validated)
        self._persist(self.editable_snapshot())
        return self.editable_snapshot()

    def reset_settings(self) -> dict[str, Any]:
        """Restore factory defaults and remove the persisted override file."""
        defaults = self._defaults()
        self._apply(defaults)
        try:
            self.user_config_file.unlink(missing_ok=True)
        except Exception:
            pass
        return self.editable_snapshot()

    def _apply(self, values: dict[str, Any]) -> None:
        for section in self._SECTIONS:
            if section in values:
                model = type(getattr(self, section))
                setattr(self, section, model(**values[section]))
        if "default_universe" in values:
            self.default_universe = [str(s).strip().upper() for s in values["default_universe"] if str(s).strip()]

    def _persist(self, values: dict[str, Any]) -> None:
        self.ensure_directories()
        self.user_config_file.write_text(
            json.dumps(values, indent=2), encoding="utf-8"
        )


# Global config instance — import this everywhere
config = AppConfig()
config.load_user_overrides()
