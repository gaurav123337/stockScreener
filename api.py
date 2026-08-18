"""FastAPI backend serving the SPA (PWA) and JSON APIs.

Run:  python api.py     (or: uvicorn api:app --host 0.0.0.0 --port 8000)
Open: http://localhost:8000

Multi-tenant: every API endpoint accepts an optional `Authorization: Bearer <token>`
header. When provided, the request is scoped to that user's preferences.
When omitted, a built-in 'guest' user is used (backward-compatible).

Robustness: every error is returned as a structured JSON response —
never an HTML error page, never an unhandled exception.
"""
from __future__ import annotations

import traceback
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Thread
from typing import Any

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Request, UploadFile, File
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from screener.bootstrap import bootstrap, get_service
from screener.core.compliance import (
    compliance_block,
    coverage_ratio,
    provenance_block,
    provider_label,
)
from screener.core.config import config
from screener.core.feedback_models import FeedbackSubmission, FeedbackWorkflowUpdate
from screener.core.interfaces import MarketDataProvider
from screener.core.responses import (
    ApiError,
    AppException,
    AuthError,
    DataSourceError,
    ErrorCodes,
    NotFoundError,
    ValidationError,
)
from screener.core.mf_models import FundScreenerRequest
from screener.core.subscription_models import subscription_store
from screener.core.user_models import UserCreate, UserLogin, UserProfile
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
    MutualFundService,
    PreferencesService,
    RecommendationService,
    RiskProfileService,
    PlanService,
    ScanService,
    ScorecardService,
    SubscriptionService,
    VerificationService,
    IndianMarketService,
)

# Wire all dependencies
bootstrap()

ROOT = Path(__file__).resolve().parent
LEGACY_WEB = ROOT / "web"
DIST = ROOT / "frontend" / "dist"
# Prefer the React build when present; fall back to the legacy vanilla SPA.
WEB = DIST if (DIST / "index.html").exists() else LEGACY_WEB

# --------------------------------------------------------------------------- #
# Lifespan (startup / shutdown)
# --------------------------------------------------------------------------- #

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: ensure guest user exists + warm the track record. Shutdown: cleanup."""
    auth = get_service(AuthService)
    auth.ensure_guest_user()
    control_center = get_service(ControlCenterService)
    control_center.load_active_config()
    control_center.bootstrap_product_owner()

    # Warm the published walk-forward backtest in the background so the first
    # page view never blocks on a multi-minute replay — and backfill its
    # signals into the verification log so /api/verify returns dated, nonzero
    # results from day one (stamped system/backtest, deduplicated on restart).
    def _warm_backtest():
        try:
            backtest = get_service(BacktestService)
            verification = get_service(VerificationService)
            if verification.has_backtest_seed():
                backtest.get()
            else:
                verification.seed_from_backtest(backtest.replay_records())
            # Warm the index series too, so the first /api/verify call reads the
            # benchmark from disk instead of a slow direct download.
            from screener.services.evaluation import load_benchmark

            load_benchmark(
                get_service(MarketDataProvider),
                config.verification.benchmark_symbol,
            )
        except Exception:
            pass

    Thread(target=_warm_backtest, daemon=True).start()

    # Phase-3: warm the mutual-fund universe (AMFI NAV feed) in the background
    # so the first screener call reads the cached universe instead of building
    # it inline. Reuses the daily disk cache, so restarts are cheap.
    def _warm_mutual_funds():
        try:
            get_service(MutualFundService).universe()
        except Exception:
            pass

    Thread(target=_warm_mutual_funds, daemon=True).start()
    yield


app = FastAPI(
    title="stockScreener",
    version="0.4.0",
    lifespan=lifespan,
    docs_url=None,       # Disable auto-docs in production
    redoc_url=None,
    openapi_url=None,
)

# CORS — allow all for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------------------------------- #
# Global exception handlers — NEVER return HTML error pages
# --------------------------------------------------------------------------- #

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """Handle our structured application exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_response(),
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle FastAPI/Starlette HTTP exceptions as JSON."""
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    code = ErrorCodes.NOT_FOUND if exc.status_code == 404 else ErrorCodes.INTERNAL_ERROR
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiError.make(code, detail).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors as structured JSON."""
    errors = exc.errors()
    messages = [f"{'.'.join(str(l) for l in e['loc'])}: {e['msg']}" for e in errors]
    return JSONResponse(
        status_code=422,
        content=ApiError.make(
            ErrorCodes.VALIDATION_ERROR,
            "Invalid request: " + "; ".join(messages),
            details={"errors": [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in errors]},
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catch-all for any unhandled exception — always returns JSON."""
    # Log the traceback server-side for debugging
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content=ApiError.make(
            ErrorCodes.INTERNAL_ERROR,
            "An unexpected error occurred. Please try again later.",
            details={"type": type(exc).__name__} if config.debug else None,
        ).model_dump(),
    )


# --------------------------------------------------------------------------- #
# Auth dependency — extract & validate Bearer token
# --------------------------------------------------------------------------- #

@app.get("/api/health", include_in_schema=False)
def health():
    """Cheap readiness probe for deployment platforms."""
    return {"status": "ok", "version": app.version}


async def get_current_user(
    authorization: str | None = Header(None),
) -> UserProfile:
    """Extract and validate the Bearer token. Returns the user profile.

    If no token is provided, returns the guest user (backward-compatible).
    If a token is provided but invalid, raises AuthError.
    """
    auth = get_service(AuthService)

    if authorization is None:
        return auth.ensure_guest_user()

    # Expect "Bearer <token>"
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthError(ErrorCodes.AUTH_INVALID, "Invalid Authorization header format. Expected 'Bearer <token>'")

    token = parts[1].strip()
    if not token:
        raise AuthError(ErrorCodes.AUTH_REQUIRED, "Token is empty")

    return auth.get_user_from_token(token)


async def require_auth(
    authorization: str | None = Header(None),
) -> UserProfile:
    """Strict auth — always requires a valid token (no guest fallback)."""
    auth = get_service(AuthService)

    if authorization is None:
        raise AuthError(ErrorCodes.AUTH_REQUIRED, "Authentication required. Please log in.")

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthError(ErrorCodes.AUTH_INVALID, "Invalid Authorization header format")

    token = parts[1].strip()
    if not token:
        raise AuthError(ErrorCodes.AUTH_REQUIRED, "Token is empty")

    return auth.get_user_from_token(token)


async def require_product_owner(user: UserProfile = Depends(require_auth)) -> UserProfile:
    if user.role != "product_owner":
        from screener.core.responses import ForbiddenError
        raise ForbiddenError("Product-owner access is required")
    return user


async def require_pro(user: UserProfile = Depends(require_auth)) -> UserProfile:
    """Strict auth + active Pro tier. The gate lives server-side."""
    from screener.services import SubscriptionService
    get_service(SubscriptionService).require_pro(user)
    return user


# --------------------------------------------------------------------------- #
# Request models
# --------------------------------------------------------------------------- #

class ScanBody(BaseModel):
    symbols: list[str] | None = None
    filter: str | None = None
    where: str | None = None
    top: int | None = Field(None, ge=1, le=500)


class UrlBody(BaseModel):
    url: str = Field(..., min_length=10, max_length=2000)


class BrokerBody(BaseModel):
    broker: str = Field(..., min_length=1, max_length=50)
    credentials: dict = Field(default_factory=dict)


class SettingsBody(BaseModel):
    patch: dict


class PreferencesBody(BaseModel):
    patch: dict


class WatchlistBody(BaseModel):
    symbols: list[str] = Field(..., max_length=200)


class RiskProfileBody(BaseModel):
    answers: dict[str, str] = Field(..., max_length=20)


class PlanBody(BaseModel):
    risk_level: str = Field(..., min_length=1, max_length=20)
    monthly_amount: float = Field(0, ge=0, le=1_000_000_000)
    horizon_years: int = Field(1, ge=0, le=80)
    goal: str = Field("wealth", max_length=30)


class FundRecommendBody(BaseModel):
    risk_level: str = Field(..., min_length=1, max_length=20)
    goal: str = Field("wealth", max_length=30)
    monthly_amount: float = Field(0, ge=0, le=1_000_000_000)
    horizon_years: int = Field(5, ge=0, le=80)


class FundCompareBody(BaseModel):
    codes: list[int] = Field(..., min_length=2, max_length=4)


class SipBody(BaseModel):
    mode: str = Field("sip", max_length=20)
    monthly_amount: float = Field(0, ge=0, le=1_000_000_000)
    lumpsum_amount: float = Field(0, ge=0, le=1_000_000_000)
    years: int = Field(10, ge=1, le=50)
    assumed_return_pct: float = Field(12, ge=0, le=60)
    step_up_pct: float = Field(0, ge=0, le=50)


class FeedbackBody(FeedbackSubmission):
    """Rich-text feedback payload from a test user."""


class AccountStatusBody(BaseModel):
    status: str
    reason: str = Field(..., min_length=3, max_length=500)


class ReasonBody(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class ConfigPublicationBody(BaseModel):
    patch: dict[str, Any]
    policies: dict[str, str] = Field(default_factory=dict)
    reason: str = Field(..., min_length=3, max_length=500)
    expected_version: int | None = Field(None, ge=0)


class RollbackBody(BaseModel):
    version: int = Field(..., ge=1)
    reason: str = Field(..., min_length=3, max_length=500)


class TokenBody(BaseModel):
    token: str = Field(..., min_length=20, max_length=256)


class EmailBody(BaseModel):
    email: str = Field(..., min_length=5, max_length=254)


class PasswordResetBody(TokenBody):
    password: str = Field(..., min_length=8, max_length=128)
    password_confirmation: str = Field(..., min_length=8, max_length=128)


# --------------------------------------------------------------------------- #
# Auth APIs
# --------------------------------------------------------------------------- #

@app.post("/api/auth/register")
def register(body: UserCreate):
    """Create a new user account."""
    auth = get_service(AuthService)
    result = auth.register(body)
    _analytics().track(result.user.user_id, "auth_register")
    return result.model_dump(mode="json")


@app.post("/api/auth/login")
def login(body: UserLogin):
    """Log in and get an access token."""
    auth = get_service(AuthService)
    result = auth.login(body)
    _analytics().track(result.user.user_id, "auth_login")
    return result.model_dump(mode="json")


@app.get("/api/auth/me")
def get_me(user: UserProfile = Depends(get_current_user)):
    """Get the current user's profile."""
    return user.model_dump(mode="json")


@app.post("/api/auth/logout")
def logout(user: UserProfile = Depends(require_auth)):
    """Log out (client-side token removal; server is stateless)."""
    return {"message": "Logged out successfully"}


@app.post("/api/auth/logout-all")
def logout_all(user: UserProfile = Depends(require_auth)):
    return get_service(AuthService).logout_all(user.user_id)


@app.post("/api/auth/verify-email")
def verify_email(body: TokenBody):
    return get_service(AuthService).verify_email(body.token).model_dump(mode="json")


@app.post("/api/auth/resend-verification")
def resend_verification(user: UserProfile = Depends(require_auth)):
    return get_service(AuthService).resend_verification(user.user_id)


@app.post("/api/auth/forgot-password")
def forgot_password(body: EmailBody):
    return get_service(AuthService).request_password_reset(body.email)


@app.post("/api/auth/reset-password")
def reset_password(body: PasswordResetBody):
    return get_service(AuthService).reset_password(
        body.token, body.password, body.password_confirmation
    )


# --------------------------------------------------------------------------- #
# Product owner control center APIs
# --------------------------------------------------------------------------- #

@app.get("/api/admin/overview")
def admin_overview(user: UserProfile = Depends(require_product_owner)):
    return get_service(ControlCenterService).dashboard()


@app.get("/api/admin/analytics")
def admin_analytics(user: UserProfile = Depends(require_product_owner)):
    """Product KPIs from the real event log + billing state.

    DAU/WAU, activation funnel, Free->Pro conversion, trial->paid, 90-day
    retention, MRR and push opt-in rate — the Phase-5 audit KPIs that were
    previously unmeasured. Computed at query time; no event source is hit.
    """
    return _analytics().overview_dict()


@app.get("/api/admin/users")
def admin_users(search: str = "", role: str | None = None, status: str | None = None,
                verified: bool | None = None,
                registered_within_days: int | None = None,
                page: int = 1, page_size: int = 25,
                user: UserProfile = Depends(require_product_owner)):
    within = registered_within_days if registered_within_days in {7, 30} else None
    return get_service(ControlCenterService).list_users(
        search=search, role=role, status=status, verified=verified,
        registered_within_days=within, page=max(page, 1), page_size=min(max(page_size, 1), 100)
    )


@app.get("/api/admin/users/{user_id}")
def admin_user_detail(user_id: str, user: UserProfile = Depends(require_product_owner)):
    return get_service(ControlCenterService).user_detail(user_id)


@app.post("/api/admin/users/{user_id}/status")
def admin_user_status(user_id: str, body: AccountStatusBody,
                      user: UserProfile = Depends(require_product_owner)):
    return get_service(ControlCenterService).set_user_status(user_id, body.status, user.user_id, body.reason)


@app.post("/api/admin/users/{user_id}/password-reset")
def admin_user_password_reset(user_id: str, body: ReasonBody,
                              user: UserProfile = Depends(require_product_owner)):
    return get_service(ControlCenterService).send_password_reset(
        user_id, user.user_id, body.reason, get_service(AuthService)
    )


@app.get("/api/admin/feedback")
def admin_feedback(search: str = "", status: str | None = None, priority: str | None = None,
                   category: str | None = None, user_id: str | None = None, assignee_id: str | None = None,
                   age: str | None = None,
                   page: int = 1, page_size: int = 25,
                   user: UserProfile = Depends(require_product_owner)):
    return get_service(ControlCenterService).list_feedback(
        search=search, status=status, priority=priority, category=category,
        user_id=user_id, assignee_id=assignee_id, age=age,
        page=max(page, 1), page_size=min(max(page_size, 1), 100)
    )


@app.get("/api/admin/feedback/{feedback_id}")
def admin_feedback_detail(feedback_id: str, user: UserProfile = Depends(require_product_owner)):
    return get_service(ControlCenterService).feedback_detail(feedback_id)


@app.post("/api/admin/feedback/{feedback_id}")
def admin_feedback_update(feedback_id: str, body: FeedbackWorkflowUpdate,
                          user: UserProfile = Depends(require_product_owner)):
    return get_service(ControlCenterService).update_feedback(feedback_id, body, user.user_id)


@app.get("/api/admin/config/registry")
def admin_config_registry(user: UserProfile = Depends(require_product_owner)):
    return {"items": get_service(ControlCenterService).registry()}


@app.get("/api/admin/config/current")
def admin_config_current(user: UserProfile = Depends(require_product_owner)):
    return get_service(ControlCenterService).current_config()


@app.post("/api/admin/config/validate")
def admin_config_validate(body: SettingsBody, user: UserProfile = Depends(require_product_owner)):
    return get_service(ControlCenterService).validate_config(body.patch)


@app.post("/api/admin/config/diff")
def admin_config_diff(body: SettingsBody, user: UserProfile = Depends(require_product_owner)):
    return get_service(ControlCenterService).config_diff(body.patch)


@app.get("/api/admin/config/history")
def admin_config_history(user: UserProfile = Depends(require_product_owner)):
    return {"items": get_service(ControlCenterService).config_history()}


@app.post("/api/admin/config/publish")
def admin_config_publish(body: ConfigPublicationBody, user: UserProfile = Depends(require_product_owner)):
    return get_service(ControlCenterService).publish_config(
        body.patch, body.policies, user.user_id, body.reason, body.expected_version
    )


@app.post("/api/admin/config/rollback")
def admin_config_rollback(body: RollbackBody, user: UserProfile = Depends(require_product_owner)):
    return get_service(ControlCenterService).rollback_config(body.version, user.user_id, body.reason)


@app.get("/api/admin/audit")
def admin_audit(action: str | None = None, target_type: str | None = None,
                page: int = 1, page_size: int = 25,
                user: UserProfile = Depends(require_product_owner)):
    return get_service(ControlCenterService).audit_event_page(
        action, target_type, max(page, 1), min(max(page_size, 1), 100)
    )


# --------------------------------------------------------------------------- #
# Preferences APIs (per-user settings)
# --------------------------------------------------------------------------- #

@app.get("/api/preferences")
def get_preferences(user: UserProfile = Depends(get_current_user)):
    """Get the current user's preferences (merged with defaults)."""
    prefs = get_service(PreferencesService)
    return prefs.get_merged_config(user.user_id)


@app.post("/api/preferences")
def update_preferences(body: PreferencesBody, user: UserProfile = Depends(get_current_user)):
    """Update the current user's preferences."""
    prefs = get_service(PreferencesService)
    return prefs.update_preferences(user.user_id, body.patch)


@app.post("/api/preferences/reset")
def reset_preferences(user: UserProfile = Depends(get_current_user)):
    """Reset the current user's preferences to system defaults."""
    prefs = get_service(PreferencesService)
    return prefs.reset_preferences(user.user_id)


@app.get("/api/preferences/watchlist")
def get_watchlist(user: UserProfile = Depends(get_current_user)):
    """Get the current user's personal watchlist."""
    prefs = get_service(PreferencesService)
    return {"symbols": prefs.get_watchlist(user.user_id)}


@app.post("/api/preferences/watchlist")
def set_watchlist(body: WatchlistBody, user: UserProfile = Depends(get_current_user)):
    """Set the current user's personal watchlist."""
    prefs = get_service(PreferencesService)
    return {"symbols": prefs.set_watchlist(user.user_id, body.symbols)}


# --------------------------------------------------------------------------- #
# Beginner-first UX: onboarding, risk profile, goal-based plan, glossary
# --------------------------------------------------------------------------- #

@app.get("/api/onboarding/questions")
def onboarding_questions(user: UserProfile = Depends(get_current_user)):
    """The plain-language risk questionnaire (no stock-market vocabulary)."""
    return {"questions": get_service(RiskProfileService).questions()}


@app.get("/api/risk-profile")
def get_risk_profile(user: UserProfile = Depends(get_current_user)):
    """The current user's saved risk profile (or null if not onboarded)."""
    profile = get_service(RiskProfileService).get_profile(user.user_id)
    return profile.model_dump(mode="json") if profile else {"level": None}


@app.post("/api/risk-profile")
def save_risk_profile(body: RiskProfileBody, user: UserProfile = Depends(get_current_user)):
    """Score and persist the user's risk profile from questionnaire answers."""
    profile = get_service(RiskProfileService).save_profile(user.user_id, body.answers)
    _analytics().track(user.user_id, "risk_profile_saved")
    return profile.model_dump(mode="json")


@app.post("/api/plan")
def build_plan(body: PlanBody, user: UserProfile = Depends(get_current_user)):
    """Build a goal-based starter basket from a risk profile + amount + horizon."""
    preferences = get_service(PreferencesService)
    effective_config = preferences.get_effective_config(user.user_id)
    try:
        plan = get_service(PlanService).build_plan(
            risk_level=body.risk_level,
            monthly_amount=body.monthly_amount,
            horizon_years=body.horizon_years,
            goal=body.goal,
            app_config=effective_config,
        )
    except Exception as e:
        raise DataSourceError(f"Plan could not be built: {e}")
    _analytics().track(
        user.user_id, "plan_built",
        risk_level=body.risk_level, horizon_years=body.horizon_years,
    )
    return plan.model_dump(mode="json")


@app.get("/api/glossary")
def get_glossary(user: UserProfile = Depends(get_current_user)):
    """Plain-language definitions for every metric a beginner might see."""
    from screener.services.plain_language import glossary
    return {"terms": glossary()}


# --------------------------------------------------------------------------- #
# Phase-3: Mutual-fund pillar (AMFI NAV feed)
# --------------------------------------------------------------------------- #

@app.get("/api/mutual-funds/status")
def mutual_fund_status(user: UserProfile = Depends(get_current_user)):
    """Universe size, data source, and last-refresh timestamp."""
    try:
        return get_service(MutualFundService).status()
    except Exception as e:
        raise DataSourceError(f"Mutual-fund data unavailable: {e}")


@app.get("/api/mutual-funds/categories")
def mutual_fund_categories(user: UserProfile = Depends(get_current_user)):
    """The beginner-friendly SEBI buckets used by the screener."""
    return {"categories": get_service(MutualFundService).categories()}


@app.get("/api/mutual-funds/screener")
def mutual_fund_screener(
    category: str = "",
    max_expense_ratio: float | None = None,
    min_aum_cr: float | None = None,
    min_return_1y: float | None = None,
    min_return_3y: float | None = None,
    min_return_5y: float | None = None,
    max_risk_rating: int | None = None,
    min_fund_age_years: float | None = None,
    manager: str = "",
    elss_only: bool = False,
    direct_only: bool = True,
    sort_by: str = "sharpe",
    sort_dir: str = "desc",
    limit: int = 50,
    offset: int = 0,
    user: UserProfile = Depends(get_current_user),
):
    """Screen the direct-plan universe by category / cost / returns / risk."""
    request = FundScreenerRequest(
        category=category or None,
        max_expense_ratio=max_expense_ratio,
        min_aum_cr=min_aum_cr,
        min_return_1y=min_return_1y,
        min_return_3y=min_return_3y,
        min_return_5y=min_return_5y,
        max_risk_rating=max_risk_rating,
        min_fund_age_years=min_fund_age_years,
        manager=manager.strip() or None,
        elss_only=elss_only,
        direct_only=direct_only,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
    try:
        result = get_service(MutualFundService).screener(request)
    except Exception as e:
        raise DataSourceError(f"Mutual-fund screener failed: {e}")
    _analytics().track(
        user.user_id, "mf_screener",
        category=category or "", direct_only=direct_only,
    )
    return result.model_dump(mode="json")


@app.get("/api/mutual-funds/{scheme_code}")
def mutual_fund_detail(scheme_code: int, user: UserProfile = Depends(get_current_user)):
    """Full scheme detail + trailing NAV history."""
    try:
        detail = get_service(MutualFundService).detail(scheme_code)
    except LookupError:
        raise NotFoundError(f"Mutual fund scheme {scheme_code} not found")
    except Exception as e:
        raise DataSourceError(f"Mutual-fund detail failed: {e}")
    return detail.model_dump(mode="json")


@app.post("/api/mutual-funds/recommend")
def mutual_fund_recommend(body: FundRecommendBody, user: UserProfile = Depends(get_current_user)):
    """A profiled direct-plan fund basket for a risk profile + goal."""
    try:
        basket = get_service(MutualFundService).recommend(
            risk_level=body.risk_level,
            goal=body.goal,
            monthly_amount=body.monthly_amount,
            horizon_years=body.horizon_years,
        )
    except ValueError as e:
        raise ValidationError(f"Invalid risk level: {e}")
    except Exception as e:
        raise DataSourceError(f"Mutual-fund recommendation failed: {e}")
    _analytics().track(
        user.user_id, "mf_recommend",
        risk_level=body.risk_level, goal=body.goal,
    )
    return basket.model_dump(mode="json")


@app.post("/api/mutual-funds/compare")
def mutual_fund_compare(body: FundCompareBody, user: UserProfile = Depends(get_current_user)):
    """Side-by-side comparison of 2-4 schemes."""
    try:
        comparison = get_service(MutualFundService).compare(body.codes)
    except Exception as e:
        raise DataSourceError(f"Mutual-fund comparison failed: {e}")
    return comparison.model_dump(mode="json")


@app.post("/api/mutual-funds/sip")
def mutual_fund_sip(body: SipBody, user: UserProfile = Depends(get_current_user)):
    """SIP / lumpsum / step-up projection (educational, not a forecast)."""
    result = get_service(MutualFundService).sip_calculator(
        mode=body.mode,
        monthly_amount=body.monthly_amount,
        lumpsum_amount=body.lumpsum_amount,
        years=body.years,
        assumed_return_pct=body.assumed_return_pct,
        step_up_pct=body.step_up_pct,
    )
    _analytics().track(user.user_id, "mf_sip", mode=body.mode)
    return result.model_dump(mode="json")



# --------------------------------------------------------------------------- #
# Feedback API
# --------------------------------------------------------------------------- #

@app.post("/api/feedback", status_code=201)
def submit_feedback(
    body: FeedbackBody,
    user: UserProfile = Depends(get_current_user),
):
    """Record tester feedback and return a receipt."""
    feedback = get_service(FeedbackService)
    record = feedback.submit(
        FeedbackSubmission.model_validate(body.model_dump()),
        user_id=user.user_id,
        username=user.username,
        reporter_email=user.email,
    )
    return {
        "feedback_id": record.feedback_id,
        "created_at": record.created_at.isoformat(),
        "message": "Feedback submitted successfully",
    }


# --------------------------------------------------------------------------- #
# Analysis APIs
# --------------------------------------------------------------------------- #

@app.get("/api/recommend/{symbol}")
def recommend(symbol: str, user: UserProfile = Depends(get_current_user)):
    """Get a recommendation for a symbol."""
    if not symbol or len(symbol) > 50:
        raise ValidationError("Invalid symbol")

    analysis = get_service(AnalysisService)
    broker = get_service(BrokerService)
    preferences = get_service(PreferencesService)
    verification = get_service(VerificationService)
    effective_config = preferences.get_effective_config(user.user_id)

    try:
        rec = analysis.analyze(symbol, effective_config)
    except Exception as e:
        raise DataSourceError(f"Unable to analyze {symbol}: {e}")

    if rec.error is not None:
        raise AppException(
            ErrorCodes.INSUFFICIENT_DATA,
            f"No recommendation is available for {symbol.upper()}: {rec.error}.",
            422,
        )

    # Use broker LTP if available
    try:
        live = broker.get_ltp(symbol)
        if live and rec.error is None:
            rec.price = round(live, 2)
    except Exception:
        pass  # Broker LTP is optional — never fail because of it

    if rec.error is None:
        try:
            verification.log_prediction(rec, user.user_id)
        except Exception:
            pass  # Logging is non-critical

    return rec.to_scan_row()


@app.post("/api/scan")
def scan(body: ScanBody, user: UserProfile = Depends(get_current_user)):
    """Scan a universe of stocks with optional filtering."""
    scan_service = get_service(ScanService)
    filter_service = get_service(FilterService)
    prefs = get_service(PreferencesService)
    effective_config = prefs.get_effective_config(user.user_id)

    # Use user's watchlist if no symbols specified
    symbols = body.symbols
    if not symbols:
        symbols = prefs.get_watchlist(user.user_id)

    predicate = None
    if body.filter:
        filter_strategy = filter_service.get_filter(body.filter)
        if not filter_strategy:
            raise ValidationError(
                f"Unknown filter '{body.filter}'",
                details={"available_filters": [f["name"] for f in filter_service.list_filters()]},
            )
        predicate = filter_strategy.matches
    elif body.where:
        try:
            expr_filter = filter_service.compile_custom(body.where)
            predicate = expr_filter.matches
        except Exception as e:
            raise ValidationError(f"Invalid expression: {e}")

    try:
        result = scan_service.scan(
            symbols,
            predicate,
            body.top,
            app_config=effective_config,
        )
    except Exception as e:
        raise DataSourceError(f"Scan failed: {e}")

    _analytics().track(
        user.user_id, "scan_run",
        matched=len(result.matched), total_scanned=result.total_scanned,
        filter=body.filter or "", has_where=bool(body.where),
    )

    # Persist the served signals so the product's track record stays auditable
    # (every call is dated and attributable to the requesting user).
    try:
        get_service(VerificationService).log_recommendations(
            result.matched, user.user_id
        )
    except Exception:
        pass  # Logging is non-critical

    # Freshness + trust framing for the whole scan (Phase-0 compliance).
    data = get_service(MarketDataProvider)
    data_updated_at = getattr(data, "history_updated_at", lambda: None)()
    provider_id = (
        getattr(data, "active_source", None)
        or getattr(data, "provider_name", None)
        or "unknown"
    )
    block = compliance_block(provider_label(provider_id))
    provenance = provenance_block(data_updated_at)

    return {
        "count": len(result.matched),
        "failed": result.failed,
        "results": [r.to_scan_row() for r in result.matched],
        "universe_size": result.total_scanned,
        "coverage": coverage_ratio(len(result.matched), result.total_scanned),
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "educational_note": block["educational_note"],
        "disclaimer": block["disclaimer"],
        "data_source": block["data_source"],
        "data_updated_at": provenance["data_updated_at"],
        "stale": provenance["stale"],
    }


@app.get("/api/filters")
def list_filters(user: UserProfile = Depends(get_current_user)):
    """List all available predefined filters."""
    filter_service = get_service(FilterService)
    return {
        "predefined": filter_service.list_filters(),
        "fields": filter_service.get_filter_fields(),
    }


@app.get("/api/recommendations")
def recommendations(
    limit: int = 10,
    action: str = "",
    user: UserProfile = Depends(get_current_user),
):
    """Top-ranked stock picks from the default universe.

    Reuses the same row shape as /api/scan so the existing results UI renders
    them unchanged. Mutual-fund picks arrive as a separate asset class later.
    """
    if limit < 1 or limit > 200:
        raise ValidationError("limit must be between 1 and 200")
    if action and action not in ("BULLISH", "NEUTRAL", "BEARISH"):
        raise ValidationError("action must be BULLISH, NEUTRAL, or BEARISH")

    prefs = get_service(PreferencesService)
    effective_config = prefs.get_effective_config(user.user_id)
    engine = get_service(RecommendationService)
    try:
        payload = engine.recommend_stocks(
            limit=limit,
            action=action or None,
            app_config=effective_config,
        )
    except Exception as e:
        raise DataSourceError(f"Recommendations failed: {e}")

    # Attach the same trust/freshness envelope as /api/scan (Phase-0).
    data = get_service(MarketDataProvider)
    data_updated_at = getattr(data, "history_updated_at", lambda: None)()
    provider_id = (
        getattr(data, "active_source", None)
        or getattr(data, "provider_name", None)
        or "unknown"
    )
    block = compliance_block(provider_label(provider_id))
    provenance = provenance_block(data_updated_at)
    payload["universe_size"] = payload.get("total_scanned", 0)
    payload["coverage"] = coverage_ratio(payload["count"], payload.get("total_scanned", 0))
    payload["scanned_at"] = datetime.now(timezone.utc).isoformat()
    payload["educational_note"] = block["educational_note"]
    payload["disclaimer"] = block["disclaimer"]
    payload["data_source"] = block["data_source"]
    payload["data_updated_at"] = provenance["data_updated_at"]
    payload["stale"] = provenance["stale"]
    return payload


@app.get("/api/compliance")
def compliance(user: UserProfile = Depends(get_current_user)):
    """Trust framing + data-source attribution for the current data state.

    The frontend fetches this once so every screen that shows a score or
    action can carry the same prominent disclaimer and last-updated stamp.
    """
    data = get_service(MarketDataProvider)
    data_updated_at = getattr(data, "history_updated_at", lambda: None)()
    return {
        **compliance_block(),
        **provenance_block(data_updated_at),
    }


@app.get("/api/data-source")
def data_source(user: UserProfile = Depends(get_current_user)):
    """Which provider is currently serving market data, and whether to show it.

    The ``show`` flag is controlled by the product owner via the control
    center config (``show_data_source``); the frontend renders the badge on
    every page only while it is enabled.
    """
    provider = get_service(MarketDataProvider)
    provider_id = (
        getattr(provider, "active_source", None)
        or getattr(provider, "provider_name", None)
        or "unknown"
    )
    return {
        "provider": provider_id,
        "label": provider_label(provider_id),
        "configured": config.market_data_provider,
        "show": bool(config.show_data_source),
    }


@app.get("/api/search")
def search(q: str = "", user: UserProfile = Depends(get_current_user)):
    """Search for a stock by symbol or company name (NSE & BSE)."""
    if not q or len(q) < 1:
        return {"query": q, "results": []}
    if len(q) > 100:
        raise ValidationError("Search query too long (max 100 characters)")

    data = get_service(MarketDataProvider)
    searcher = getattr(data, "search", None)
    if not callable(searcher):
        return {"query": q, "results": []}

    try:
        return {"query": q, "results": searcher(q)}
    except Exception:
        return {"query": q, "results": [], "warning": "Search temporarily unavailable"}


@app.get("/api/verify")
def verify(user: UserProfile = Depends(get_current_user)):
    """Verify past predictions against historical prices.

    The evaluation window is rolling: every logged signal is measured at each
    configured horizon (30/90/365 days) as soon as that horizon has elapsed, so
    the reported hit-rates are dated and recompute as more history accrues.
    """
    verification = get_service(VerificationService)
    try:
        return verification.verify().model_dump(mode="json")
    except Exception as e:
        raise DataSourceError(f"Verification failed: {e}")


# --------------------------------------------------------------------------- #
# Published track record (walk-forward backtest)
# --------------------------------------------------------------------------- #

@app.get("/api/backtest")
def backtest(user: UserProfile = Depends(get_current_user)):
    """Published walk-forward track record of the signal engine.

    Serves the cached report (regenerated automatically when stale); a cold
    cache is recomputed on demand. This is the Stockopedia-style evidence the
    "Signal Score" claims rest on.
    """
    try:
        return get_service(BacktestService).get().model_dump(mode="json")
    except Exception as e:
        raise DataSourceError(f"Backtest unavailable: {e}")


@app.post("/api/backtest/run")
def backtest_run(user: UserProfile = Depends(require_product_owner)):
    """Force a fresh walk-forward replay and republish the track record."""
    try:
        return get_service(BacktestService).run().model_dump(mode="json")
    except Exception as e:
        raise DataSourceError(f"Backtest failed: {e}")


# --------------------------------------------------------------------------- #
# Learn moat — beginner explainers served as JSON (and as SEO pages below)
# --------------------------------------------------------------------------- #

@app.get("/api/learn")
def learn_list(q: str = "", category: str | None = None):
    """Catalogue of beginner explainer articles (the SEO/content moat)."""
    articles = get_service(ContentService).search(q) if q else get_service(ContentService).list_articles()
    if category:
        articles = [a for a in articles if a.get("category") == category]
    return {"articles": articles, "count": len(articles)}


@app.get("/api/learn/{slug}")
def learn_detail(slug: str):
    """Full article body for the in-app reader."""
    article = get_service(ContentService).get_article(slug)
    return article.model_dump(mode="json")


def _render_article_page(slug: str) -> str | None:
    """Server-render a full HTML page for SEO crawlers and link-sharers."""
    from html import escape

    from screener.core.content_models import Article

    try:
        article: Article = get_service(ContentService).get_article(slug)
    except Exception:
        return None
    meta_desc = escape(article.seo_meta.get("description", article.excerpt(155)))
    title = escape(article.title)
    sections_html = []
    for section in article.sections:
        paras = "".join(f"<p>{escape(p)}</p>" for p in section.body.split("\n\n") if p.strip())
        bullets = ""
        if section.bullets:
            items = "".join(f"<li>{escape(b)}</li>" for b in section.bullets)
            bullets = f"<ul>{items}</ul>"
        sections_html.append(
            f"<section><h2>{escape(section.heading)}</h2>{paras}{bullets}</section>"
        )
    related_links = "".join(
        f'<a href="/learn/{escape(rel)}">{escape(rel)}</a>' for rel in article.related_slugs
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — stockScreener Learn</title>
<meta name="description" content="{meta_desc}">
</head>
<body>
<header><a href="/learn">&larr; Learn hub</a></header>
<main>
<h1>{title}</h1>
<p class="tagline">{escape(article.tagline)}</p>
<p class="meta">{article.reading_minutes} min read · {escape(article.category)}</p>
{"".join(sections_html)}
<section class="related"><h2>Keep learning</h2>{related_links}</section>
</main>
<footer>Educational content. Not investment advice.</footer>
</body>
</html>"""


@app.get("/learn", response_class=HTMLResponse)
def learn_hub():
    """Server-rendered list of all explainer articles (SEO landing page)."""
    from html import escape

    cards = []
    for a in get_service(ContentService).list_articles():
        desc = escape(a["excerpt"])
        cards.append(
            f'<article><h2><a href="/learn/{a["slug"]}">{escape(a["title"])}</a></h2>'
            f'<p>{desc}</p><p class="meta">{a["reading_minutes"]} min · {escape(a["category"])}</p></article>'
        )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Learn — stockScreener</title>
<meta name="description" content="Beginner guides to Indian stock-market concepts: P/E ratio, index funds vs ETFs, ELSS tax saving, the Signal Score and drawdowns.">
</head>
<body>
<header><h1>Learn</h1></header>
<main>{"".join(cards)}</main>
<footer>Educational content. Not investment advice.</footer>
</body>
</html>"""


@app.get("/learn/{slug}", response_class=HTMLResponse)
def learn_page(slug: str):
    """Server-rendered article page for SEO crawlers and link-sharers."""
    page = _render_article_page(slug)
    if page is None:
        raise NotFoundError("Article not found")
    return page


# --------------------------------------------------------------------------- #
# Proof layer — monthly scorecard + illustrative success stories
# --------------------------------------------------------------------------- #

@app.get("/api/scorecard")
def scorecard(user: UserProfile = Depends(get_current_user)):
    """Published monthly track record (backtest + live verification log)."""
    try:
        return get_service(ScorecardService).monthly_scorecard()
    except Exception as e:
        raise DataSourceError(f"Scorecard unavailable: {e}")


@app.post("/api/scorecard/refresh")
def scorecard_refresh(user: UserProfile = Depends(require_product_owner)):
    """Force regeneration of the monthly scorecard (slow, admin-only)."""
    try:
        return get_service(ScorecardService).refresh()
    except Exception as e:
        raise DataSourceError(f"Scorecard refresh failed: {e}")


@app.get("/api/stories")
def success_stories(user: UserProfile = Depends(get_current_user)):
    """Illustrative educational walkthroughs — explicitly not real users."""
    return {"stories": get_service(ScorecardService).success_stories()}


# --------------------------------------------------------------------------- #
# Indian market research APIs (optional, server-side provider)
# --------------------------------------------------------------------------- #

def _indian_market() -> IndianMarketService:
    return get_service(IndianMarketService)


@app.get("/api/indian-market/status")
def indian_market_status(user: UserProfile = Depends(require_product_owner)):
    """Expose rollout health without returning provider secrets or payloads."""
    return _indian_market().rollout_status()


@app.get("/api/indian-market/stock")
def indian_stock(q: str = "", user: UserProfile = Depends(require_auth)):
    return _indian_market().stock(q)


@app.get("/api/indian-market/industry-search")
def indian_industry_search(q: str = "", user: UserProfile = Depends(require_auth)):
    return _indian_market().search("industry_search", q)


@app.get("/api/indian-market/mutual-funds/search")
def indian_mutual_fund_search(q: str = "", user: UserProfile = Depends(require_auth)):
    return _indian_market().search("mutual_fund_search", q)


@app.get("/api/indian-market/overview")
def indian_overview(user: UserProfile = Depends(require_auth)):
    service = _indian_market()
    snapshots: dict[str, Any] = {}
    warnings: list[str] = []
    fetched_at: str | None = None
    for endpoint in (
        "trending", "52_week_high_low", "nse_most_active",
        "bse_most_active", "price_shockers", "commodities",
    ):
        try:
            result = service.snapshot(endpoint)
            snapshots[endpoint] = result["data"]
            fetched_at = fetched_at or result["fetched_at"]
            warnings.extend(result.get("warnings", []))
        except DataSourceError as exc:
            warnings.append(f"{endpoint}: {exc}")
    return {
        "data": {"snapshots": snapshots},
        "provider": "indian_api",
        "fetched_at": fetched_at or datetime.now(timezone.utc).isoformat(),
        "stale": False,
        "warnings": warnings,
    }


@app.get("/api/indian-market/stock/{stock_id}/history")
def indian_history(
    stock_id: str,
    period: str = "1Y",
    filter: str = "price",
    user: UserProfile = Depends(require_auth),
):
    if len(period) > 20 or len(filter) > 50:
        raise ValidationError("Invalid historical query parameters")
    return _indian_market().history(stock_id, period=period, filter=filter)


@app.get("/api/indian-market/stock/{stock_id}/stats")
def indian_stats(
    stock_id: str,
    stats: str = "",
    user: UserProfile = Depends(require_auth),
):
    if len(stats) > 100:
        raise ValidationError("Invalid stats query parameter")
    return _indian_market().stats(stock_id, stats=stats)


@app.get("/api/indian-market/stock/{stock_id}/recommendations")
def indian_recommendations(stock_id: str, user: UserProfile = Depends(require_auth)):
    return _indian_market().analysis("stock_target_price", stock_id)


@app.get("/api/indian-market/stock/{stock_id}/forecasts")
def indian_forecasts(
    stock_id: str,
    measure_code: str = "",
    period_type: str = "",
    data_type: str = "",
    age: str = "",
    user: UserProfile = Depends(require_auth),
):
    query = {key: value for key, value in {
        "measure_code": measure_code, "period_type": period_type,
        "data_type": data_type, "age": age,
    }.items() if value}
    if any(len(value) > 100 for value in query.values()):
        raise ValidationError("Invalid forecast query parameter")
    return _indian_market().analysis("stock_forecasts", stock_id, **query)


# --------------------------------------------------------------------------- #
# Settings / Dashboard APIs (system-level; per-user via /api/preferences)
# --------------------------------------------------------------------------- #

@app.get("/api/settings")
def get_settings(user: UserProfile = Depends(get_current_user)):
    """Current value of every dashboard-editable setting (user's effective config)."""
    prefs = get_service(PreferencesService)
    return prefs.get_merged_config(user.user_id)


@app.get("/api/settings/defaults")
def get_settings_defaults(user: UserProfile = Depends(get_current_user)):
    """Factory defaults (for the UI 'reset to default' reference)."""
    return config._defaults()


@app.post("/api/settings")
def update_settings(body: SettingsBody, user: UserProfile = Depends(get_current_user)):
    """Apply a partial settings patch (user-scoped)."""
    prefs = get_service(PreferencesService)
    return prefs.update_preferences(user.user_id, body.patch)


@app.post("/api/settings/reset")
def reset_settings(user: UserProfile = Depends(get_current_user)):
    """Restore factory defaults for the current user."""
    prefs = get_service(PreferencesService)
    return prefs.reset_preferences(user.user_id)


# --------------------------------------------------------------------------- #
# Knowledge / Training APIs
# --------------------------------------------------------------------------- #

@app.post("/api/learn/file")
async def learn_file(
    file: UploadFile = File(...),
    user: UserProfile = Depends(get_current_user),
):
    """Upload a file to ingest into the knowledge base."""
    knowledge = get_service(KnowledgeService)

    # Validate file extension
    allowed = config.knowledge.allowed_extensions
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in allowed:
        raise ValidationError(
            f"Unsupported file type '{suffix}'. Allowed: {', '.join(sorted(allowed))}",
            details={"allowed_extensions": sorted(allowed)},
        )

    # Limit file size (10 MB)
    MAX_SIZE = 10 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise ValidationError("File too large (max 10 MB)")

    # Save to temp file then ingest
    temp_path = config.knowledge_dir / (file.filename or "upload")
    try:
        temp_path.write_bytes(content)
        result = knowledge.learn_from_file(temp_path)
        return result.model_dump(mode="json")
    except Exception as e:
        raise AppException(ErrorCodes.INGESTION_ERROR, f"Failed to ingest file: {e}", 500)
    finally:
        # Clean up temp file
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass


@app.post("/api/learn/url")
def learn_url(body: UrlBody, user: UserProfile = Depends(get_current_user)):
    """Ingest knowledge from a URL."""
    knowledge = get_service(KnowledgeService)
    try:
        result = knowledge.learn_from_url(body.url)
        return result.model_dump(mode="json")
    except Exception as e:
        raise AppException(ErrorCodes.INGESTION_ERROR, f"Failed to ingest URL: {e}", 500)


@app.post("/api/learn")
def learn_now(user: UserProfile = Depends(get_current_user)):
    """Ingest all files from the knowledge directory."""
    knowledge = get_service(KnowledgeService)
    try:
        result = knowledge.learn_from_directory()
        return result.model_dump(mode="json")
    except Exception as e:
        raise AppException(ErrorCodes.INGESTION_ERROR, f"Learning failed: {e}", 500)


@app.get("/api/knowledge")
def get_knowledge(user: UserProfile = Depends(get_current_user)):
    """Get the current knowledge base content."""
    knowledge = get_service(KnowledgeService)
    try:
        return {
            "path": str(config.kb_file),
            "content": knowledge.get_knowledge_content(),
        }
    except Exception as e:
        raise AppException(ErrorCodes.INGESTION_ERROR, f"Failed to read knowledge base: {e}", 500)


# --------------------------------------------------------------------------- #
# Broker APIs
# --------------------------------------------------------------------------- #

@app.get("/api/brokers/instructions")
def broker_instructions(user: UserProfile = Depends(get_current_user)):
    """Get connection instructions for all brokers."""
    broker = get_service(BrokerService)
    try:
        return broker.get_instructions()
    except Exception as e:
        raise AppException(ErrorCodes.BROKER_ERROR, f"Failed to get instructions: {e}", 500)


@app.get("/api/brokers/status")
def broker_status(user: UserProfile = Depends(get_current_user)):
    """Get connection status for all brokers."""
    broker = get_service(BrokerService)
    try:
        return broker.get_status()
    except Exception as e:
        raise AppException(ErrorCodes.BROKER_ERROR, f"Failed to get status: {e}", 500)


@app.post("/api/brokers/connect")
def broker_connect(body: BrokerBody, user: UserProfile = Depends(get_current_user)):
    """Connect a broker with credentials."""
    broker = get_service(BrokerService)
    try:
        return broker.connect(body.broker, body.credentials)
    except Exception as e:
        raise AppException(ErrorCodes.BROKER_ERROR, f"Connection failed: {e}", 500)


@app.post("/api/brokers/disconnect/{broker_name}")
def broker_disconnect(broker_name: str, user: UserProfile = Depends(get_current_user)):
    """Disconnect a broker."""
    service = get_service(BrokerService)
    try:
        return service.disconnect(broker_name)
    except Exception as e:
        raise AppException(ErrorCodes.BROKER_ERROR, f"Disconnect failed: {e}", 500)


@app.get("/api/brokers/holdings")
def broker_holdings(user: UserProfile = Depends(get_current_user)):
    """Get holdings from connected broker."""
    broker = get_service(BrokerService)
    try:
        return broker.get_holdings()
    except Exception as e:
        raise AppException(ErrorCodes.BROKER_ERROR, f"Failed to fetch holdings: {e}", 500)


# --------------------------------------------------------------------------- #
# Freemium / Pro billing (Phase 4)
# --------------------------------------------------------------------------- #

def _billing() -> SubscriptionService:
    return get_service(SubscriptionService)


def _analytics() -> AnalyticsService:
    return get_service(AnalyticsService)


class CheckoutBody(BaseModel):
    plan_id: str = Field(..., min_length=3, max_length=40)


class SaveScreenBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    filter_expr: str = ""
    sort_by: str = "score"
    sort_dir: str = "desc"
    limit: int = Field(50, ge=1, le=500)
    alert_enabled: bool = False
    alert_email: str | None = Field(None, max_length=254)


class HoldingsBody(BaseModel):
    holdings: list[dict[str, Any]] = Field(..., min_length=1, max_length=200)


class StrategyBacktestBody(BaseModel):
    strategy: str = Field(..., min_length=1, max_length=60)
    symbols: list[str] | None = None


class TierBody(BaseModel):
    tier: str = Field(..., min_length=3, max_length=10)


@app.get("/api/billing/plans")
def billing_plans(user: UserProfile = Depends(get_current_user)):
    """Public plan catalog (pricing + feature list)."""
    return {"plans": _billing().plans()}


@app.get("/api/billing/entitlements")
def billing_entitlements(user: UserProfile = Depends(require_auth)):
    """The requesting user's effective entitlements (server-authoritative)."""
    return _billing().entitlements(user).model_dump(mode="json")


@app.post("/api/billing/checkout")
def billing_checkout(body: CheckoutBody, user: UserProfile = Depends(require_auth)):
    """Open a checkout session for a plan (unpaid until confirmed)."""
    result = _billing().create_checkout(user, body.plan_id)
    _analytics().track(user.user_id, "checkout_created", plan_id=body.plan_id)
    return result


@app.post("/api/billing/checkout/{session_id}/confirm")
def billing_confirm(session_id: str, user: UserProfile = Depends(require_auth)):
    """Settle a checkout session. Grants Pro when the gateway reports paid."""
    result = _billing().confirm_checkout(user, session_id)
    _analytics().track(
        user.user_id, "checkout_paid",
        plan_id=result.get("plan_id") or "", session_id=session_id,
    )
    return result


@app.get("/api/billing/subscription")
def billing_subscription(user: UserProfile = Depends(require_auth)):
    """Current subscription state + active flag."""
    return _billing().current_subscription(user)


@app.post("/api/billing/cancel")
def billing_cancel(user: UserProfile = Depends(require_auth)):
    """Cancel at renewal (Pro keeps working until renews_at)."""
    return _billing().cancel_subscription(user)


# Admin tier management (product-owner only)
@app.post("/api/admin/users/{user_id}/tier")
def admin_user_tier(user_id: str, body: TierBody, user: UserProfile = Depends(require_product_owner)):
    """Set a user's tier (free/pro) — direct grant or immediate revoke."""
    return _billing().admin_set_tier(user_id, body.tier)


# --------------------------------------------------------------------------- #
# Pro: saved screens + email alerts
# --------------------------------------------------------------------------- #

@app.get("/api/pro/screens")
def pro_list_screens(user: UserProfile = Depends(require_auth)):
    """List my saved screens (Free tier can hold one, Pro unlimited)."""
    return {"screens": _billing().list_screens(user)}


@app.post("/api/pro/screens")
def pro_save_screen(body: SaveScreenBody, user: UserProfile = Depends(require_auth)):
    """Save a screen; alerts require Pro."""
    return _billing().save_screen(
        user,
        name=body.name,
        filter_expr=body.filter_expr,
        sort_by=body.sort_by,
        sort_dir=body.sort_dir,
        limit=body.limit,
        alert_enabled=body.alert_enabled,
        alert_email=body.alert_email,
    )


@app.delete("/api/pro/screens/{screen_id}")
def pro_delete_screen(screen_id: str, user: UserProfile = Depends(require_auth)):
    """Delete one of my saved screens."""
    return _billing().delete_screen(user, screen_id)


@app.post("/api/pro/screens/{screen_id}/evaluate")
def pro_evaluate_screen(screen_id: str, user: UserProfile = Depends(require_pro)):
    """Run a saved screen against the live universe and dispatch an alert."""
    return _billing().evaluate_screen(user, screen_id)


# --------------------------------------------------------------------------- #
# Pro: portfolio analytics + per-strategy deep backtest
# --------------------------------------------------------------------------- #

@app.post("/api/pro/portfolio/analytics")
def pro_portfolio_analytics(body: HoldingsBody, user: UserProfile = Depends(require_pro)):
    """Aggregate analytics for a user-declared holding list."""
    return _billing().portfolio_analytics(user, body.holdings)


@app.post("/api/pro/strategy/backtest")
def pro_strategy_backtest(body: StrategyBacktestBody, user: UserProfile = Depends(require_pro)):
    """Focused per-strategy walk-forward replay on requested symbols."""
    return _billing().strategy_backtest(user, body.strategy, body.symbols)


# --------------------------------------------------------------------------- #
# Alerts (Phase 5) — price, screen-hit and MF-NAV threshold rules
# --------------------------------------------------------------------------- #

class AlertRuleBody(BaseModel):
    rule_type: str = Field(..., min_length=3, max_length=20)
    name: str | None = Field(None, max_length=120)
    symbol: str | None = Field(None, max_length=20)
    scheme_code: str | None = Field(None, max_length=20)
    direction: str = "above"
    trigger_value: float = Field(..., ge=0)
    screen_id: str | None = Field(None, max_length=64)
    enabled: bool = True


def _alerts() -> AlertService:
    return get_service(AlertService)


@app.get("/api/alerts")
def alerts_list(user: UserProfile = Depends(require_pro)):
    """List my alert rules (Pro)."""
    return {"rules": [r.model_dump(mode="json") for r in _alerts().list_rules(user)]}


@app.post("/api/alerts")
def alerts_create(body: AlertRuleBody, user: UserProfile = Depends(require_pro)):
    """Create an alert rule (price, screen_hit or mf_nav)."""
    rule = _alerts().create_rule(user, body.model_dump())
    _analytics().track(user.user_id, "alert_created", rule_type=rule.rule_type.value)
    return rule.model_dump(mode="json")


@app.delete("/api/alerts/{alert_id}")
def alerts_delete(alert_id: str, user: UserProfile = Depends(require_pro)):
    """Delete one of my alert rules."""
    deleted = _alerts().delete_rule(user, alert_id)
    if not deleted:
        raise NotFoundError("Alert not found")
    return {"deleted": True}


@app.post("/api/alerts/{alert_id}/reset")
def alerts_reset(alert_id: str, user: UserProfile = Depends(require_pro)):
    """Re-arm a fired alert so it can fire again (one-shot semantics)."""
    reset = _alerts().reset_rule(user, alert_id)
    if not reset:
        raise NotFoundError("Alert not found")
    return {"reset": True}


@app.post("/api/alerts/evaluate")
def alerts_evaluate(symbols: list[str] = Body(default=[]), user: UserProfile = Depends(require_pro)):
    """Run all my enabled rules against the live market; report fired alerts.

    ``symbols`` optionally bounds the universe (watchlist-first). Each rule is
    one-shot until reset, so this endpoint never spams.
    """
    return {"fired": _alerts().evaluate_user_alerts(user, symbols)}


# --------------------------------------------------------------------------- #
# PWA push subscriptions (Phase 5) — opt-in browser notifications
# --------------------------------------------------------------------------- #

class PushSubscribeBody(BaseModel):
    endpoint: str = Field(..., min_length=8, max_length=512)
    p256dh: str = ""
    auth: str = ""
    user_agent: str = ""


@app.get("/api/push/public-key")
def push_public_key():
    """VAPID public key for the service worker (base64url, no padding)."""
    return {"public_key": config.push.vapid_public_key}


@app.post("/api/push/subscribe")
def push_subscribe(body: PushSubscribeBody, user: UserProfile = Depends(require_auth)):
    """Register this browser endpoint for push notifications."""
    from screener.core.subscription_models import PushSubscription

    sub = PushSubscription(
        user_id=user.user_id,
        endpoint=body.endpoint,
        p256dh=body.p256dh,
        auth=body.auth,
        user_agent=body.user_agent,
    )
    subscription_store.upsert_push_subscription(sub)
    _analytics().track(user.user_id, "push_opt_in")
    return {"subscribed": True}


@app.delete("/api/push/subscribe")
def push_unsubscribe(endpoint: str, user: UserProfile = Depends(require_auth)):
    """Remove this browser endpoint (called when the SW unsubscribes)."""
    subscription_store.delete_push_subscription(endpoint)
    return {"unsubscribed": True}


# --------------------------------------------------------------------------- #
# Check-before-buy (Phase 5) — research checklist + broker deep-links
# --------------------------------------------------------------------------- #

def _check() -> CheckBeforeBuyService:
    return get_service(CheckBeforeBuyService)


@app.get("/api/check/brokers")
def check_brokers(user: UserProfile = Depends(get_current_user)):
    """Brokers we can deep-link to (review-only; never order placement)."""
    return {"brokers": _check().brokers()}


@app.get("/api/check/deep-link/{broker_id}")
def check_deep_link(broker_id: str, symbol: str, user: UserProfile = Depends(get_current_user)):
    """Review-only deep-link to the symbol page in a user's broker app."""
    return _check().broker_deep_link(broker_id, symbol)


@app.get("/api/check/{symbol}")
def check_before_buy(symbol: str, user: UserProfile = Depends(get_current_user)):
    """Pre-trade checklist for a symbol (price vs plan, valuation, sizing)."""
    if not symbol or len(symbol) > 50:
        raise ValidationError("Invalid symbol")
    analysis = get_service(AnalysisService)
    preferences = get_service(PreferencesService)
    effective_config = preferences.get_effective_config(user.user_id)
    try:
        rec = analysis.analyze(symbol, effective_config)
    except Exception as e:
        raise DataSourceError(f"Unable to analyze {symbol}: {e}")
    if rec.error is not None:
        raise AppException(
            ErrorCodes.INSUFFICIENT_DATA,
            f"No checklist is available for {symbol.upper()}: {rec.error}.",
            422,
        )
    return _check().checklist(user, rec)


# --------------------------------------------------------------------------- #
# Feedback loop (Phase 5) — instrumented outcomes + published changelog
# --------------------------------------------------------------------------- #

def _feedback_loop() -> FeedbackLoopService:
    return get_service(FeedbackLoopService)


class PublishChangeBody(BaseModel):
    version: str = "1.0.0"
    date: str | None = None
    title: str = Field(..., min_length=3, max_length=120)
    summary: str = ""
    weight_changes: dict[str, dict[str, Any]] = Field(default_factory=dict)


@app.get("/api/feedback-loop/outcomes")
def feedback_outcomes(user: UserProfile = Depends(get_current_user)):
    """Instrumented per-band hit rates from matured signals."""
    return _feedback_loop().outcome_stats()


@app.get("/api/feedback-loop/suggestions")
def feedback_suggestions(user: UserProfile = Depends(get_current_user)):
    """Suggested weight changes — returned for review, never auto-applied."""
    return _feedback_loop().weight_suggestions()


@app.get("/api/feedback-loop/changelog")
def feedback_changelog(user: UserProfile = Depends(get_current_user)):
    """Publicly published scoring-model changes (transparency ledger)."""
    return {"entries": _feedback_loop().changelog()}


@app.post("/api/feedback-loop/publish")
def feedback_publish(body: PublishChangeBody, user: UserProfile = Depends(require_product_owner)):
    """Record a reviewed weight change in the published changelog (PO only)."""
    entry = _feedback_loop().publish_change(user, body.model_dump())
    return entry.model_dump(mode="json")


# --------------------------------------------------------------------------- #
# SPA + static + PWA assets
# --------------------------------------------------------------------------- #

@app.get("/manifest.json")
def manifest():
    # Vite PWA emits manifest.webmanifest; the legacy SPA used manifest.json.
    candidate = WEB / "manifest.webmanifest"
    if not candidate.exists():
        candidate = WEB / "manifest.json"
    return FileResponse(candidate)


@app.get("/sw.js")
def service_worker():
    return FileResponse(WEB / "sw.js", media_type="application/javascript", headers={"Cache-Control": "no-cache"})


@app.get("/{full_path:path}")
def spa(full_path: str):
    if full_path == "api" or full_path.startswith("api/"):
        raise NotFoundError(f"API route '/{full_path}' was not found")
    # serve real files if they exist (css/js/icons), else index.html (SPA routing)
    candidate = WEB / full_path
    if full_path and candidate.exists() and candidate.is_file():
        headers = {}
        # Hashed build assets are immutable; index.html/sw.js must revalidate.
        if full_path.startswith("assets/") and Path(full_path).suffix in {".js", ".css", ".svg", ".png", ".woff2", ".ico"}:
            headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif full_path == "index.html":
            headers["Cache-Control"] = "no-cache"
        return FileResponse(candidate, headers=headers)
    # A missing asset must 404, not fall back to index.html — otherwise a
    # stale cached index.html referencing an old hashed chunk would receive
    # HTML for a JS import and fail with "Failed to fetch dynamically
    # imported module".
    if full_path and Path(full_path).suffix:
        raise NotFoundError(f"Asset '{full_path}' was not found")
    return FileResponse(WEB / "index.html", headers={"Cache-Control": "no-cache"})


# Legacy vanilla SPA keeps its assets under web/static; the Vite build emits
# hashed assets under dist/assets (served by the catch-all above).
if LEGACY_WEB.exists() and not (DIST / "index.html").exists():
    app.mount("/static", StaticFiles(directory=LEGACY_WEB / "static"), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
