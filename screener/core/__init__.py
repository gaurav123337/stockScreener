"""Core framework: config, models, interfaces, DI container, plugin registry."""
from screener.core.config import AppConfig, config
from screener.core.container import Container, container
from screener.core.models import (
    Action,
    BrokerStatus,
    Holding,
    LearnResult,
    Outcome,
    PredictionRecord,
    Recommendation,
    ScanResult,
    StockMetrics,
    VerificationReport,
)
from screener.core.interfaces import (
    BrokerAdapter,
    EventBus,
    FilterStrategy,
    KnowledgeStore,
    MarketDataProvider,
    PredictionRepository,
    ScoringStrategy,
)
from screener.core.plugins import PluginRegistry, registry

__all__ = [
    "AppConfig",
    "config",
    "Container",
    "container",
    "Action",
    "BrokerStatus",
    "Holding",
    "LearnResult",
    "Outcome",
    "PredictionRecord",
    "Recommendation",
    "ScanResult",
    "StockMetrics",
    "VerificationReport",
    "BrokerAdapter",
    "EventBus",
    "FilterStrategy",
    "KnowledgeStore",
    "MarketDataProvider",
    "PredictionRepository",
    "ScoringStrategy",
    "PluginRegistry",
    "registry",
]
