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
from screener.infrastructure.data.amfi_client import AmfiClient
from screener.infrastructure.data.yahoo_provider import YahooDataProvider
from screener.infrastructure.data.indian_api_client import IndianApiClient
from screener.infrastructure.data.indian_data_provider import IndianDataProvider
from screener.infrastructure.data.hybrid_provider import HybridDataProvider
from screener.infrastructure.data.yahoo_indian_provider import YahooIndianProvider
from screener.infrastructure.persistence.csv_repository import (
    CSVPredictionRepository,
    MarkdownKnowledgeStore,
)
from screener.services import (
    AnalysisService,
    AlertService,
    AnalyticsService,
    AuthService,
    BacktestService,
    BrokerService,
    CheckBeforeBuyService,
    ContentService,
    ControlCenterService,
    FeedbackLoopService,
    FeedbackService,
    FilterService,
    KnowledgeService,
    PreferencesService,
    RecommendationService,
    RiskProfileService,
    PlanService,
    ScanService,
    ScorecardService,
    SubscriptionService,
    VerificationService,
    IndianMarketService,
    MutualFundService,
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
    container.register(MarketDataProvider, factory=_market_data_provider)
    container.register(IndianMarketGateway, factory=_indian_gateway)
    container.register(PredictionRepository, CSVPredictionRepository)
    container.register(KnowledgeStore, MarkdownKnowledgeStore)
    # Services
    container.register(AnalysisService, AnalysisService)
    container.register(AlertService, AlertService)
    container.register(AnalyticsService, AnalyticsService)
    container.register(ScanService, ScanService)
    container.register(VerificationService, VerificationService)
    container.register(BacktestService, BacktestService)
    container.register(KnowledgeService, KnowledgeService)
    container.register(FilterService, FilterService)
    container.register(BrokerService, BrokerService)
    container.register(CheckBeforeBuyService, CheckBeforeBuyService)
    container.register(ControlCenterService, ControlCenterService)
    container.register(ContentService, ContentService)
    container.register(FeedbackLoopService, FeedbackLoopService)
    # Feedback is persisted to SQLite and retrieved through the protected
    # Product Owner API. Email is intentionally not part of the request path.
    container.register(FeedbackService, FeedbackService)
    container.register(AuthService, AuthService)
    container.register(PreferencesService, PreferencesService)
    container.register(RecommendationService, RecommendationService)
    container.register(RiskProfileService, RiskProfileService)
    container.register(PlanService, PlanService)
    container.register(SubscriptionService, SubscriptionService)
    container.register(ScorecardService, ScorecardService)
    container.register(IndianMarketService, factory=lambda: IndianMarketService(get_service(IndianMarketGateway)))
    container.register(
        MutualFundService,
        factory=lambda: MutualFundService(client=AmfiClient()),
    )


def get_service(service_type):
    """Convenience accessor for a service."""
    return container.resolve(service_type)


def refresh_providers() -> None:
    """Re-register config-driven providers after a config publish.

    The DI container caches singletons, so a runtime change to
    ``market_data_provider`` / ``indian_market_provider`` only takes effect
    once the affected provider instances are re-registered. Consumers resolve
    lazily (``_provider``), so the next call picks up the new adapter.
    """
    container.register_instance(MarketDataProvider, _market_data_provider())
    container.register_instance(IndianMarketGateway, _indian_gateway())


def _market_data_provider():
    """Build the core market-data provider selected by configuration.

    ``config.market_data_provider`` picks the adapter behind the whole
    screener: ``yahoo`` (default), ``indian_api``, or ``hybrid`` (Yahoo with
    per-symbol Indian API fallback). Swapping is a configuration change only.
    """
    choice = config.market_data_provider
    if choice == "indian_api":
        return IndianDataProvider(client=IndianApiClient(config.indian_api))
    if choice == "hybrid":
        return HybridDataProvider(
            primary=YahooDataProvider(),
            fallback=IndianDataProvider(client=IndianApiClient(config.indian_api)),
        )
    return YahooDataProvider()


def _indian_gateway():
    """Build the Indian market adapter selected by configuration.

    Both adapters implement the same core gateway contract, so swapping the
    provider (e.g. indian_api -> yahoo) is a configuration change only.
    """
    if config.indian_market_provider == "yahoo":
        return YahooIndianProvider(data_provider=get_service(MarketDataProvider))
    return IndianApiClient(config.indian_api)
