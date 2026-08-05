"""Application Bootstrapper — wires all dependencies at startup.

Import this module once (e.g., in api.py or main.py) before using services.
"""
from __future__ import annotations

from screener.core.config import config
from screener.core.container import container
from screener.core.interfaces import (
    KnowledgeStore,
    MarketDataProvider,
    PredictionRepository,
)
from screener.infrastructure.data.yahoo_provider import YahooDataProvider
from screener.infrastructure.data.indian_api_client import IndianApiClient
from screener.infrastructure.data.yahoo_indian_provider import YahooIndianProvider
from screener.infrastructure.persistence.csv_repository import (
    CSVPredictionRepository,
    MarkdownKnowledgeStore,
)
from screener.services import (
    AnalysisService,
    AuthService,
    BacktestService,
    BrokerService,
    ControlCenterService,
    FeedbackService,
    FilterService,
    KnowledgeService,
    PreferencesService,
    RecommendationService,
    ScanService,
    VerificationService,
    IndianMarketService,
)
from screener.core.indian_market import IndianMarketGateway


def bootstrap(environment: str | None = None) -> None:
    """Register all services in the DI container.

    Call this once at application startup. Safe to call multiple times.
    """
    if environment:
        config.environment = environment

    config.ensure_directories()

    # Infrastructure
    container.register(MarketDataProvider, YahooDataProvider)
    container.register(IndianMarketGateway, factory=_indian_gateway)
    container.register(PredictionRepository, CSVPredictionRepository)
    container.register(KnowledgeStore, MarkdownKnowledgeStore)
    # Services
    container.register(AnalysisService, AnalysisService)
    container.register(ScanService, ScanService)
    container.register(VerificationService, VerificationService)
    container.register(BacktestService, BacktestService)
    container.register(KnowledgeService, KnowledgeService)
    container.register(FilterService, FilterService)
    container.register(BrokerService, BrokerService)
    container.register(ControlCenterService, ControlCenterService)
    # Feedback is persisted to SQLite and retrieved through the protected
    # Product Owner API. Email is intentionally not part of the request path.
    container.register(FeedbackService, FeedbackService)
    container.register(AuthService, AuthService)
    container.register(PreferencesService, PreferencesService)
    container.register(RecommendationService, RecommendationService)
    container.register(IndianMarketService, factory=lambda: IndianMarketService(get_service(IndianMarketGateway)))


def get_service(service_type):
    """Convenience accessor for a service."""
    return container.resolve(service_type)


def _indian_gateway():
    """Build the Indian market adapter selected by configuration.

    Both adapters implement the same core gateway contract, so swapping the
    provider (e.g. indian_api -> yahoo) is a configuration change only.
    """
    if config.indian_market_provider == "yahoo":
        return YahooIndianProvider(data_provider=get_service(MarketDataProvider))
    return IndianApiClient(config.indian_api)
