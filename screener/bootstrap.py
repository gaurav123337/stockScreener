"""Application Bootstrapper — wires all dependencies at startup.

Import this module once (e.g., in api.py or main.py) before using services.
"""
from __future__ import annotations

from screener.core.config import config
from screener.core.container import container
from screener.core.interfaces import (
    FeedbackNotifier,
    KnowledgeStore,
    MarketDataProvider,
    PredictionRepository,
)
from screener.infrastructure.data.yahoo_provider import YahooDataProvider
from screener.infrastructure.notifications import ResendFeedbackNotifier
from screener.infrastructure.persistence.csv_repository import (
    CSVPredictionRepository,
    MarkdownKnowledgeStore,
)
from screener.services import (
    AnalysisService,
    AuthService,
    BrokerService,
    ControlCenterService,
    FeedbackService,
    FilterService,
    KnowledgeService,
    PreferencesService,
    ScanService,
    VerificationService,
)


def bootstrap(environment: str | None = None) -> None:
    """Register all services in the DI container.

    Call this once at application startup. Safe to call multiple times.
    """
    if environment:
        config.environment = environment

    config.ensure_directories()

    # Infrastructure
    container.register(MarketDataProvider, YahooDataProvider)
    container.register(PredictionRepository, CSVPredictionRepository)
    container.register(KnowledgeStore, MarkdownKnowledgeStore)
    container.register(FeedbackNotifier, factory=ResendFeedbackNotifier.from_environment)

    # Services
    container.register(AnalysisService, AnalysisService)
    container.register(ScanService, ScanService)
    container.register(VerificationService, VerificationService)
    container.register(KnowledgeService, KnowledgeService)
    container.register(FilterService, FilterService)
    container.register(BrokerService, BrokerService)
    container.register(ControlCenterService, ControlCenterService)
    container.register(
        FeedbackService,
        factory=lambda: FeedbackService(notifier=container.resolve(FeedbackNotifier)),
    )
    container.register(AuthService, AuthService)
    container.register(PreferencesService, PreferencesService)


def get_service(service_type):
    """Convenience accessor for a service."""
    return container.resolve(service_type)
