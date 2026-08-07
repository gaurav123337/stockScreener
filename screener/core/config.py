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

from screener import universe

# Bumped whenever a persisted default changes meaning; used to migrate stale
# `data/user_config.json` files created by older versions.
_CONFIG_VERSION = 2


class DataConfig(BaseSettings):
    """Data fetching configuration."""
    model_config = SettingsConfigDict(env_prefix="SCREENER_DATA_")

    default_period: str = "1y"
    default_interval: str = "1d"
    retry_attempts: int = 2
    retry_pause_seconds: float = 1.0
    max_workers: int = 8
    # Minimum rows of OHLCV history required before a symbol is analysable.
    min_history_rows: int = 60
    # Long-period fallback used when a symbol has insufficient 1y history.
    fallback_period: str = "2y"
    # Fundamentals change slowly; cache them this long to avoid re-scraping.
    fundamentals_cache_ttl_seconds: int = 86_400
    # How long fetched OHLCV history is reused before re-fetching. This is the
    # rate-limit layer: repeated scans of the same universe hit the cache, not
    # the price provider.
    history_cache_ttl_seconds: int = 3600


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
    # Every logged signal is evaluated over each of these horizons.
    horizons: list[int] = Field(default_factory=lambda: [30, 90, 365])
    # Benchmark index used for "vs market" comparison.
    benchmark_symbol: str = "^NSEI"
    # Minimum sample size before a hit-rate is considered meaningful/public.
    min_sample: int = 20


class BacktestConfig(BaseSettings):
    """Walk-forward backtest replay of the signal engine."""
    model_config = SettingsConfigDict(env_prefix="SCREENER_BACKTEST_")

    # Signals are generated on these dates and evaluated over each horizon.
    start_date: str = "2024-01-01"
    sample_every_days: int = 21
    max_horizon_days: int = 365
    # Published report freshness (how long /api/backtest may serve cached data).
    cache_ttl_seconds: int = 43_200
    universe: list[str] = Field(default_factory=lambda: list(universe.NIFTY50))


class IndianApiConfig(BaseSettings):
    """Deployment-managed settings for the optional Indian market API."""
    model_config = SettingsConfigDict(env_prefix="SCREENER_INDIAN_API_")

    enabled: bool = True
    base_url: str = "https://stock.indianapi.in"
    api_key: str = Field(default="sk-live-HzojagKyU5z1OuWNQ6tGWtJU2M5XlsjvEyL6jbU9", repr=False)
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


class MutualFundConfig(BaseSettings):
    """Phase-3 mutual-fund data (AMFI NAV feed, mirrored by mfapi.in)."""
    model_config = SettingsConfigDict(env_prefix="SCREENER_MF_")

    enabled: bool = True
    # Free mirror of the official AMFI NAV data (scheme master + daily NAVs
    # + historical NAV series + SEBI scheme category). AMFI's own endpoint is
    # frequently unreachable from datacenter IPs, so the mirror is the
    # reliable free source; the data itself is the AMFI NAV file.
    base_url: str = "https://api.mfapi.in"
    timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    # How long the cached scheme universe / scheme details stay fresh.
    # Daily refresh (AMFI publishes NAV once a day) with visible timestamps.
    cache_ttl_seconds: int = Field(default=86_400, ge=300, le=604_800)
    max_workers: int = Field(default=8, ge=1, le=32)
    # Universe caps so a first build stays fast and polite to the feed.
    universe_max: int = Field(default=220, ge=20, le=800)
    per_category_max: int = Field(default=40, ge=5, le=200)
    per_amc_per_category: int = Field(default=6, ge=1, le=50)
    # Risk-free rate used for Sharpe/Sortino (approx 10-yr g-sec yield).
    risk_free_rate: float = Field(default=0.065, ge=0, le=0.20)


class ComplianceConfig(BaseSettings):
    """Trust / compliance framing surfaced alongside every recommendation.

    Kept as configuration (not hardcoded UI text) so the product owner can
    tune the wording without a deploy. This is deliberate — the disclaimer is
    part of the product's trust surface, not an afterthought.
    """
    model_config = SettingsConfigDict(env_prefix="SCREENER_COMPLIANCE_")

    # Leading statement framing the tool as education, not advice.
    educational_note: str = (
        "Educational tool for research, not SEBI-registered investment advice. "
        "Nothing here is a recommendation to buy or sell any security."
    )
    # Shown prominently whenever scores / actions are displayed.
    disclaimer: str = (
        "Scores are generated by a rules-based engine and are not a guarantee "
        "of future returns. Do your own research before investing."
    )
    # Attribution for the underlying data sources.
    data_source_label: str = (
        "Data: Yahoo Finance (prices & fundamentals) + NSE (company metadata)."
    )


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
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    compliance: ComplianceConfig = Field(default_factory=ComplianceConfig)
    indian_api: IndianApiConfig = Field(default_factory=IndianApiConfig)
    mutual_fund: MutualFundConfig = Field(default_factory=MutualFundConfig)
    market_data_provider: Literal["yahoo", "indian_api", "hybrid"] = "yahoo"

    # Which adapter backs the Indian market workspace. Both providers conform
    # to the same gateway contract, so this is the only switch that changes.
    indian_market_provider: Literal["indian_api", "yahoo"] = "indian_api"

    # Environment
    environment: Literal["development", "production", "testing"] = "development"
    debug: bool = False

    # Default symbol universe — Nifty 500 (falls back to Nifty 50 if the
    # vendored NSE constituents file is unavailable).
    default_universe: list[str] = Field(default_factory=lambda: [
        *universe.default_universe(),
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

    @property
    def backtest_report_file(self) -> Path:
        return self.data_dir / "backtest_report.json"

    # ---- Phase-3 mutual-fund cache paths ----
    @property
    def mf_dir(self) -> Path:
        return self.data_dir / "mf"

    @property
    def mf_master_file(self) -> Path:
        return self.mf_dir / "master.json"

    @property
    def mf_universe_file(self) -> Path:
        return self.mf_dir / "universe.json"

    @property
    def mf_scheme_dir(self) -> Path:
        return self.mf_dir / "schemes"

    def mf_scheme_file(self, scheme_code: int) -> Path:
        return self.mf_scheme_dir / f"{scheme_code}.json"

    def ensure_directories(self) -> None:
        """Create all required directories if they don't exist."""
        for d in (self.data_dir, self.knowledge_dir, self.knowledge_graph_dir, self.mf_dir, self.mf_scheme_dir):
            d.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Dashboard-editable settings (get / update / reset)
    # ------------------------------------------------------------------ #
    _SECTIONS = ("data", "scoring", "risk", "knowledge", "verification", "compliance")

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
                    self._migrate(saved)
                    self._apply(saved)
                    # Persist the migrated state so the fix is applied once.
                    self._persist(saved)
        except Exception:
            pass  # corrupt file -> keep booting with defaults

    def _migrate(self, saved: dict[str, Any]) -> None:
        """Upgrade stale persisted settings to current defaults.

        v2: the default screening universe grew from Nifty 50 to Nifty 500.
        A persisted ``default_universe`` that still equals the legacy Nifty-50
        list is almost certainly a stale snapshot, not a deliberate choice —
        replace it with the current default. Custom universes are preserved.
        """
        if int(saved.get("config_version", 1)) < 2:
            existing = saved.get("default_universe")
            if isinstance(existing, list):
                normalized = [str(s).strip().upper() for s in existing if str(s).strip()]
                if sorted(normalized) == sorted(universe.NIFTY50):
                    saved["default_universe"] = list(universe.default_universe())
        saved["config_version"] = _CONFIG_VERSION

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
        out = dict(values)
        out["config_version"] = _CONFIG_VERSION
        self.user_config_file.write_text(
            json.dumps(out, indent=2), encoding="utf-8"
        )


# Global config instance — import this everywhere
config = AppConfig()
config.load_user_overrides()
