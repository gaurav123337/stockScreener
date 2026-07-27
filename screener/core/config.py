"""Centralized configuration management using Pydantic Settings.

All application settings in one place, environment-variable aware,
and type-validated. No more scattered hardcoded values.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

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

    def ensure_directories(self) -> None:
        """Create all required directories if they don't exist."""
        for d in (self.data_dir, self.knowledge_dir, self.knowledge_graph_dir):
            d.mkdir(parents=True, exist_ok=True)


# Global config instance — import this everywhere
config = AppConfig()
