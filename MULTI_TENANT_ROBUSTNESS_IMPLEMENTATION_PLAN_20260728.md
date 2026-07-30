# Multi-Tenant & Robustness Implementation Plan

**Timestamp:** **2026-07-28T04:34:41.000Z (UTC) | 28-07-2026 10:04:41 (IST)**

---

## Overview

Transform stockScreener from a single-user application into a **multi-tenant platform** where each user can register, log in, and maintain their own preferences (scoring thresholds, risk parameters, watchlists, filter presets). Additionally, add a **robust error-handling layer** so that every API response is a well-formed, user-friendly message — no crashes, no hallucinated data, no silent failures.

---

## Current State Analysis

### What exists today
- **Single global config** (`screener/core/config.py`) — one `user_config.json` for everyone; no concept of users.
- **No authentication** — all API endpoints are open; no sessions, no tokens.
- **No per-user data isolation** — predictions, broker settings, knowledge are shared.
- **Inconsistent error handling** — some endpoints return `{"error": "..."}` with 400, others throw unhandled exceptions (500 HTML page).
- **No input validation middleware** — malformed JSON, missing fields, oversized payloads can crash endpoints.
- **No graceful degradation** — if Yahoo Finance is down, the API returns raw exceptions.

### Architecture (v0.3.0)
```
api.py (FastAPI) → services/ → core/ → infrastructure/
```

---

## Implementation Phases

### Phase 1: Multi-Tenant Foundation (Backend)
| # | Task | Files | Details |
|---|------|-------|---------|
| 1.1 | User model + database | `screener/core/user_models.py` | Pydantic model for user, SQLite-backed store |
| 1.2 | Auth service | `screener/services/auth_service.py` | Register, login, logout, token generation/validation (JWT-style) |
| 1.3 | Per-user preferences store | `screener/services/preferences_service.py` | CRUD for per-user settings (scoring, risk, watchlist, etc.) |
| 1.4 | Auth middleware | `api.py` | Dependency injection to extract & validate tokens, inject user context |
| 1.5 | Per-user config scoping | `screener/core/config.py` | `get_user_config(user_id)` — overlay user prefs on defaults |

### Phase 2: Robustness Layer (Backend)
| # | Task | Files | Details |
|---|------|-------|---------|
| 2.1 | Global exception handler | `api.py` | Catch all unhandled exceptions → structured JSON error |
| 2.2 | Standardized error responses | `screener/core/responses.py` | `ApiResponse`, `ErrorResponse` models with codes |
| 2.3 | Input validation middleware | `api.py` | Content-length limits, JSON body validation, request timeouts |
| 2.4 | Service-level error wrapping | All services | Never raise raw exceptions; return `Result` types with error messages |
| 2.5 | Graceful degradation | `screener/infrastructure/data/yahoo_provider.py` | Timeout, retry, circuit-breaker for external data calls |

### Phase 3: API Endpoint Updates
| # | Task | Files | Details |
|---|------|-------|---------|
| 3.1 | Auth endpoints | `api.py` | `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout` |
| 3.2 | Preferences endpoints | `api.py` | `GET/PUT /api/preferences` (per-user settings) |
| 3.3 | Protect existing endpoints | `api.py` | All `/api/*` endpoints require valid token; inject user context |
| 3.4 | Per-user settings | `api.py` | `/api/settings` reads/writes user-specific overrides |

### Phase 4: Frontend Updates
| # | Task | Files | Details |
|---|------|-------|---------|
| 4.1 | Auth context + pages | `frontend/src/features/auth/` | Login, Register, Logout |
| 4.2 | Token management | `frontend/src/api/client.ts` | Store token, attach to requests, handle 401 |
| 4.3 | Preferences UI | `frontend/src/features/settings/` | User-specific settings page |
| 4.4 | Error boundary | `frontend/src/app/` | Global error boundary, toast notifications for API errors |
| 4.5 | Route guards | `frontend/src/app/router.tsx` | Redirect to login when unauthenticated |

### Phase 5: Testing & Validation
| # | Task | Files | Details |
|---|------|-------|---------|
| 5.1 | Unit tests for auth | `tests/test_auth.py` | Register, login, token validation |
| 5.2 | Unit tests for preferences | `tests/test_preferences.py` | Per-user CRUD |
| 5.3 | Integration tests | `tests/test_multi_tenant.py` | End-to-end multi-user scenarios |
| 5.4 | Robustness tests | `tests/test_robustness.py` | Error injection, timeout handling |

---

## Technical Considerations

### Data Storage
- **SQLite** (single-file, zero-config) for user accounts and per-user preferences.
- File: `data/users.db` — created automatically on first run.
- Per-user config stored as JSON blobs keyed by `user_id`.

### Authentication
- **Token-based auth** (JWT-like, signed with a server secret).
- Token stored in `localStorage` on frontend; sent via `Authorization: Bearer <token>` header.
- Tokens expire after 7 days (configurable).
- No password hashing with external library — use `hashlib.pbkdf2_hmac` (stdlib).

### Backward Compatibility
- **CLI mode** (`main.py`) continues to work without auth (single-user fallback).
- Existing `config` behavior is preserved as the "system default"; user prefs overlay on top.
- If no users exist, the API creates a default `guest` user automatically.

### Robustness Principles
1. **Never crash** — every exception is caught and converted to a structured JSON error.
2. **Always validate** — every input is validated before processing.
3. **Graceful degradation** — if external data fails, return cached/default data with a warning, not a 500.
4. **Informative errors** — every error has a `code`, `message`, and optional `details`.
5. **No hallucination** — the system never fabricates data; if it can't produce a result, it says so clearly.

---

## Success Criteria

- [ ] Two users can register and log in independently.
- [ ] Each user sees only their own preferences and settings.
- [ ] No API endpoint ever returns an unhandled 500 HTML error page.
- [ ] Every error response is `{"error": {"code": "...", "message": "..."}}` with an appropriate HTTP status.
- [ ] The system continues to function (with appropriate messages) even when Yahoo Finance is unreachable.
- [ ] CLI mode still works without any auth.
- [ ] All existing tests pass without modification.

---

## Next Steps

1. Create user/auth models and database layer.
2. Implement auth service with token management.
3. Build preferences service for per-user settings.
4. Add global error handling middleware to FastAPI.
5. Update all API endpoints with auth + error handling.
6. Update frontend with auth pages and token management.
7. Write tests.

---

## Update - 30-07-2026

**Timestamp:** **2026-07-30T04:55:00Z (UTC) | 30-07-2026 10:25:00 (IST)**

### Completed in this continuation

- Registered `AuthService` and `PreferencesService` in the application container so API startup and auth dependencies resolve.
- Passed a request-scoped `AppConfig` through recommendation and scan services. Scoring thresholds, scoring weights, risk parameters, scan worker count, and default universe can now vary by user without mutating the process-global config.
- Added strict nested preference validation and deterministic symbol normalization/de-duplication.
- Changed the recommendation API to return structured `INSUFFICIENT_DATA` responses instead of exposing a HOLD row with zero-valued market data.
- Cleared the frontend query cache on login, registration, logout, and invalid-session handling to prevent cached tenant data from crossing identities.
- Added offline tests for preference isolation, effective-config behavior, invalid preferences, and insufficient-data behavior.
- Ensured SQLite connections close deterministically and unknown `/api/*` routes return structured JSON instead of the SPA HTML shell.

### Remaining scope

- Prediction history, broker credentials/connections, and learned knowledge are still shared infrastructure and require tenant keys or tenant-specific repositories before they can be considered isolated.
- Request size limits, end-to-end timeouts, external-provider circuit breaking, and broader API integration tests remain open robustness work.
- Guest fallback remains enabled for backward compatibility; strict authentication for all tenant data requires a product decision and migration plan.
