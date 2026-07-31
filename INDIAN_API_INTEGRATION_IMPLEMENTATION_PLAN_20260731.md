# Indian API Integration Implementation Plan

**Timestamp:** **2026-07-31T17:14:45Z (UTC) | 31-07-2026 22:44:45 (IST)**

## Overview

Integrate `indianapi.in` as a configurable Indian-market data source for
stockScreener, while preserving the existing Yahoo Finance implementation and
the dependency direction documented in `ARCHITECTURE.md`. The integration
should expose useful Indian API capabilities through a focused UI and make
future provider changes possible by changing configuration, adapters, and
endpoint metadata rather than rewriting business logic or pages.

Phase 1 implementation has now started with configuration, provider-neutral
contracts, an injectable HTTP client, endpoint metadata, normalization, and
offline tests. Live authentication and upstream compatibility remain deferred
until the provider's base URL and authentication convention are confirmed.

## Goal, Deliverables, and Constraints

### Goal

Provide a reliable provider abstraction and user-facing Indian market workspace
for discovery, market snapshots, stock details, historical analysis, and
analyst/forecast data.

### Deliverables

- Configurable `IndianApiClient` in infrastructure with authentication,
  timeout, retry, rate-limit, and structured error handling.
- Provider-neutral contracts and application services for supported Indian API
  use cases.
- Central endpoint catalog and typed request/response DTOs/mappers so endpoint
  changes remain localized.
- Provider selection/fallback policy that does not break existing Yahoo-based
  recommendations, scans, verification, or broker features.
- FastAPI routes under a dedicated `/api/indian-market` namespace.
- React UI with search, market overview, stock detail, historical chart/stats,
  forecasts, and analyst recommendations.
- Unit, contract/fixture, API, and frontend tests; documentation for local and
  Render deployment configuration.

### Constraints

- Preserve `Presentation → Application → Domain ← Infrastructure`.
- Do not expose API keys or upstream credentials to the browser or persist
  them in user preferences.
- Keep Yahoo Finance as the current default until Indian API parity and
  reliability are verified; use explicit provider configuration rather than
  silently changing existing behavior.
- Normalize upstream numeric strings, dates, nulls, and inconsistent response
  envelopes at the infrastructure boundary.
- Treat upstream data as informational market data, not investment advice.
- Avoid making the supplied documentation's illustrative response shapes part
  of the core domain until verified against live responses.

## Current State Analysis

### Backend

- `screener/core/interfaces.py` defines `MarketDataProvider` with only
  `fetch_history`, `fetch_info`, and `normalize_symbol`.
- `screener/infrastructure/data/yahoo_provider.py` implements that contract
  using `yfinance`, including NSE/BSE normalization and fallback.
- `screener/bootstrap.py` registers `YahooDataProvider` directly in the DI
  container.
- `screener/core/config.py` contains typed environment-aware settings and a
  persisted dashboard configuration mechanism. Its editable registry currently
  covers data, scoring, risk, knowledge, verification, and the default
  universe, but no upstream API credentials.
- `api.py` uses thin handlers and service resolution through `get_service()`.
  Existing routes include recommendation, scan, search, verification, user
  settings, and product-owner configuration.

### Frontend

- React + TypeScript + Vite uses `createHashRouter` in
  `frontend/src/app/router.tsx` and lazy-loaded feature pages.
- `frontend/src/app/layout/AppLayout.tsx` has primary navigation for
  Recommended, Scan, Train, and Broker, with Settings/Guide/Feedback in a
  secondary menu.
- `frontend/src/api/client.ts` and `frontend/src/api/endpoints.ts` centralize
  HTTP calls; React Query is used for server state.
- Existing reusable UI primitives include `Card`, `Button`, `PageHeader`,
  `Spinner`, table helpers, and the scan autocomplete/results patterns.
- The product-owner configuration page uses versioned global configuration,
  but upstream secrets must remain deployment-managed.

## API Surface from the Supplied Documentation

### Phase 1: high-value, low-ambiguity endpoints

| Capability              | Upstream endpoint                      | Proposed UI                 |
| ----------------------- | -------------------------------------- | --------------------------- |
| Company lookup/details  | `/stock?name=`                         | Search and stock detail     |
| Industry discovery      | `/industry_search?query=`              | Search results/filter       |
| Mutual-fund discovery   | `/mutual_fund_search?query=`           | Search results              |
| Trending gainers/losers | `/trending`                            | Market overview             |
| 52-week high/low        | `/fetch_52_week_high_low_data`         | Market overview             |
| NSE/BSE most active     | `/NSE_most_active`, `/BSE_most_active` | Market overview             |
| Price shockers          | `/price_shockers`                      | Market overview             |
| Commodity futures       | `/commodities`                         | Optional overview tab       |
| Historical price data   | `/historical_data`                     | Stock chart                 |
| Historical stats        | `/historical_stats`                    | Financial-statistics tables |

### Phase 2: richer analytical endpoints

- `/stock_target_price?stock_id=` for target prices and recommendation
  snapshots.
- `/stock_forecasts` with `stock_id`, `measure_code`, `period_type`,
  `data_type`, and `age` selectors.
- `/mutual_funds` for categorized NAV, returns, asset size, and star ratings.

The first implementation should prioritize the stock, trending, activity,
historical, and search workflows. Forecasts and recommendations should follow
once live payloads and identifiers are confirmed.

## Important Documentation Gaps / Validation Spike

Before production implementation, verify these items with a disposable API key
and recorded fixtures:

1. **Base URL and authentication:** the supplied file lists paths but not the
   host URL, API-key header/query convention, quota, or subscription limits.
2. **Parameter inconsistency:** historical data describes `stock_name` but its
   example uses `symbol`; this must be tested and standardized in our adapter.
3. **Identifier semantics:** `/stock` returns `tickerId`, industry search
   returns multiple IDs/codes, while forecasts and target prices require
   `stock_id`.
4. **Response shape variance:** recommendation snapshots are described as
   arrays in one place and wrapped objects in the example; several fields are
   strings in trending responses and numbers elsewhere.
5. **Error and empty-market behavior:** define handling for 404, 429, 5xx,
   malformed JSON, and documented empty lists while the market is closed.
6. **Date/time and exchange conventions:** normalize timezone-aware timestamps,
   expiry dates, `NSE`/`BSE`, and `.NS`/`.BO`/RIC identifiers.
7. **Terms and caching:** confirm permitted caching, redistribution, polling
   frequency, and UI attribution requirements from the provider's current
   terms.

Deliverable of this spike: sanitized JSON fixtures, a short compatibility
matrix, and a go/no-go decision for each endpoint.

## Proposed Architecture

### Domain contracts

Add provider-neutral contracts in `screener/core` without importing HTTP or
provider-specific code:

- `IndianMarketGateway` (or a broader `MarketResearchGateway`) with explicit
  methods for company detail, discovery, snapshots, historical datasets,
  historical stats, target prices, and forecasts.
- Small domain DTOs for `StockSummary`, `MarketSnapshot`, `HistoricalSeries`,
  `HistoricalStats`, `RecommendationSummary`, and `ForecastQuery`.
- Typed enums for period, historical filter, stats type, forecast measure,
  period type, data type, and data age.

Do not model every large nested `/stock` object up front. Preserve verified
unknown subtrees as validated dictionaries where the UI does not yet consume
them, and promote fields to typed DTOs as fixture coverage grows.

### Infrastructure adapter

Create `screener/infrastructure/data/indian_api_client.py` (or a dedicated
`indian_api/` package) responsible for:

- `requests.Session` with base URL, API-key auth, user-agent, connect/read
  timeouts, retry/backoff, and correlation logging.
- One generic request method that maps upstream errors to `DataSourceError`.
- An endpoint catalog containing path, method, query schema, cache TTL, and
  parser name; no scattered URL literals in services or UI.
- Parsers/mappers for each supported response shape, including string-to-number
  conversion, null removal, date parsing, and wrapped/list variants.
- Optional short-lived server-side caching and request coalescing to protect
  quota and improve dashboard load time.

### Application services and provider policy

- Add `IndianMarketService` to orchestrate use cases and return stable DTOs.
- Add a provider registry/policy in core/application configuration:
  `yahoo`, `indian_api`, or `hybrid` by capability. The existing
  `MarketDataProvider` can remain the scan/recommendation contract initially;
  the richer Indian gateway should be separate to avoid forcing Yahoo to
  implement unrelated endpoints.
- Wire implementations only in `screener/bootstrap.py`.
- Keep existing services unchanged in phase 1. Later, if desired, add an
  explicit `data.provider` setting and an adapter that maps Indian API stock
  detail into the existing recommendation/scan input contract.

### Configuration model

Deployment-managed values in `AppConfig` / environment variables:

- `SCREENER_INDIAN_API_ENABLED`
- `SCREENER_INDIAN_API_BASE_URL`
- `SCREENER_INDIAN_API_KEY` (secret; never returned by settings endpoints)
- `SCREENER_INDIAN_API_TIMEOUT_SECONDS`
- `SCREENER_INDIAN_API_RETRY_ATTEMPTS`
- `SCREENER_INDIAN_API_CACHE_TTL_SECONDS`
- `SCREENER_INDIAN_API_RATE_LIMIT_PER_MINUTE`
- `SCREENER_MARKET_DATA_PROVIDER` (`yahoo`, `indian_api`, `hybrid`)

Safe product-owner configuration may include enablement, provider preference,
cache TTL bounds, and endpoint feature flags, but not the key/base deployment
secret. Add these fields to the configuration registry only with sensitivity,
scope, restart, and user-overridable metadata.

## Proposed API Routes

Keep handlers thin and authenticated through the existing user dependency:

- `GET /api/indian-market/stock?q=`
- `GET /api/indian-market/industry-search?q=`
- `GET /api/indian-market/mutual-funds/search?q=`
- `GET /api/indian-market/overview`
- `GET /api/indian-market/stock/{stock_id}/history?period=&filter=`
- `GET /api/indian-market/stock/{stock_id}/stats?stats=`
- `GET /api/indian-market/stock/{stock_id}/recommendations`
- `GET /api/indian-market/stock/{stock_id}/forecasts?...`

Route models should validate allowed enum values and bounded pagination/limits.
The server should return a stable envelope with `data`, `provider`, `fetched_at`,
and optional `stale`/`warnings` fields, while preserving structured errors.

## Proposed UI

Add a lazy `IndianMarketPage` at `/indian-market`, linked from primary or
secondary navigation depending on product priority.

### Workspace layout

- Header: provider status, last-updated time, refresh action, and attribution.
- Search box with debounced company/industry/mutual-fund modes and autocomplete.
- Overview cards: top gainers, top losers, NSE/BSE most active, price shockers,
  and 52-week highs/lows; tabs for commodities and mutual funds if enabled.
- Stock detail route or selected-stock panel: current NSE/BSE prices, percent
  change, year range, company/sector, key metrics, analyst view, risk meter,
  news, and corporate actions where available.
- Historical chart using normalized series with period/filter controls.
- Stats tables for quarterly results, year-over-year results, balance sheet,
  cash flow, ratios, and shareholding patterns.
- Forecast/recommendation panels with explicit “source and as-of” labels;
  recommendation numbers mapped to Buy/Outperform/Hold/Underperform/Sell.
- Consistent loading, empty-market, stale-cache, provider-disabled, rate-limit,
  and error states; responsive cards/tables following existing design tokens.

Do not place the API key in Vite environment variables or browser requests.

## Implementation Phases

### Phase 0 — Contract and access validation (0.5–1 day)

- Confirm authentication, base URL, quota, terms, and live endpoint behavior.
- Capture sanitized fixtures and resolve parameter/identifier inconsistencies.
- Decide which Phase 1 endpoints are production-safe.

### Phase 1 — Config, client, contracts, and tests (1.5–2 days)

- Add typed config and secret redaction rules.
- Add gateway contracts, DTOs, endpoint catalog, HTTP client, error mapping,
  parsers, retry policy, and bounded caching.
- Add fixture-based parser tests and mocked HTTP contract tests.

### Phase 2 — Service, DI, and backend routes (1–1.5 days)

- Implement `IndianMarketService` and register it in bootstrap.
- Add stable API response envelopes and endpoint handlers.
- Add auth, validation, disabled-provider, empty-market, upstream-error, and
  cache behavior tests.

### Phase 3 — UI workspace (2–3 days)

- Add route, navigation item, API endpoint functions, TypeScript types, and
  React Query hooks.
- Build overview, search, stock detail, chart, stats, and analytical panels.
- Add responsive/accessibility states and source/as-of attribution.

### Phase 4 — Provider integration and rollout (1 day)

- Deploy key/base URL through Render secrets/environment configuration.
- Run smoke tests in a non-production environment during open and closed
  market conditions.
- Enable by feature flag, monitor errors/latency/quota, then decide whether to
  expose Indian API data in existing scan/recommendation flows.

## Testing Strategy

- **Unit:** config validation, symbol/ID normalization, enum validation,
  number/date parsing, recommendation mapping, cache policy, error mapping.
- **Contract fixtures:** representative success, empty, 404, 429, 5xx,
  malformed, wrapped-array, and null-containing payloads.
- **Backend API:** authentication, query validation, provider-disabled mode,
  stable response envelope, and no-secret leakage.
- **Frontend:** route rendering, debounced search, query controls, chart/table
  mapping, stale/error/empty states, mobile layout, and keyboard accessibility.
- **Integration smoke:** live-key checks outside normal unit tests, never in CI;
  redact all upstream credentials and response data as appropriate.

## Risks and Mitigations

| Risk                                 | Mitigation                                                  |
| ------------------------------------ | ----------------------------------------------------------- |
| Documentation is incomplete or stale | Phase-0 compatibility spike and fixtures                    |
| Upstream schema drift                | Endpoint catalog, tolerant boundary parsers, contract tests |
| API quota/rate limits                | Server-side cache, backoff, refresh throttling, metrics     |
| Sensitive key exposure               | Backend-only client, redacted config, secret scanning       |
| Mixing provider semantics            | Provider-neutral DTOs and explicit provider labels          |
| Market closed/partial data           | Empty/stale states and fetched-at timestamps                |
| Existing flow regression             | Keep Yahoo default and add dedicated routes first           |
| Misleading recommendations           | Source, timestamp, and informational disclaimer             |

## Success Criteria

- Indian API can be enabled/disabled through deployment configuration without
  code edits or browser secret exposure.
- Changing endpoint paths, auth headers, or response shapes is localized to the
  client/catalog/mappers and tests.
- Existing Yahoo-backed tests and user workflows continue to pass unchanged.
- Authenticated users can use the Indian Market workspace for verified Phase-1
  capabilities with clear loading, stale, empty, and error states.
- No upstream credentials appear in API responses, persisted user settings,
  frontend bundles, logs, or audit records.
- Parser/API/frontend quality gates pass, and live smoke checks are documented.
- Provider attribution, fetched time, and non-advice wording are visible in the
  UI.

## Next Steps

1. Obtain the Indian API key and confirm the official base URL/authentication
   instructions.
2. Run the Phase-0 validation spike against each candidate endpoint.
3. Approve the endpoint compatibility matrix and Phase-1 scope.
4. Switch to implementation mode and execute Phases 1–4 incrementally.

## Completion Summary

- Created this implementation plan from
  `knowledge_graph/indian_api_stock_market.md` and the current repository
  architecture.
- No production code, configuration, or frontend files were modified.
- The plan intentionally leaves live authentication and endpoint compatibility
  as an explicit prerequisite because those details are absent from the
  supplied documentation.

## Update – Phase 1 implementation started (2026-07-31)

- Added `IndianApiConfig` with deployment-only secret handling and bounded
  timeout/retry/cache/rate-limit settings.
- Added provider-neutral contracts in `screener/core/indian_market.py`.
- Added `IndianApiClient` with centralized endpoint metadata, injectable
  session, retry behavior, TTL cache, structured errors, and tolerant numeric
  normalization. It is intentionally not wired into existing Yahoo flows yet.
- Added offline tests in `tests/test_indian_api.py` covering mapping, cache,
  disabled/error behavior, auth-header placement, and secret redaction.
- The assumed `X-Api-Key` header is provisional and must be confirmed before
  any live smoke test.

## Update – Phase 3 UI implementation (2026-07-31)

### Scope

- Add a lazy `/indian-market` workspace without changing Yahoo-backed flows.
- Consume only the authenticated backend namespace; no API credential is sent
  to Vite or the browser.
- Keep provider payload subtrees tolerant (`unknown`/record types) until live
  fixtures confirm stable field names.

### UI decisions

- React Query owns overview, lookup, and selected-stock analytical requests.
- The page exposes market snapshots, stock lookup, historical data, stats,
  recommendations, and forecasts with explicit source/time metadata.
- An inline SVG chart avoids adding a dependency for the first provider-neutral
  visualization and remains keyboard/screen-reader friendly.
- Disabled, empty, stale, loading, and error states are rendered as normal
  product states, not silently swallowed.

### Phase 3 checklist

- [x] Typed API wrappers and query hooks.
- [x] Lazy route, navigation, and responsive workspace.
- [x] Search, overview cards, chart, stats, and analysis panels.
- [x] Frontend build and regression validation.

### Completion Summary

- Added `frontend/src/features/indian-market/IndianMarketPage.tsx` with
  provider attribution, source timestamps, responsive cards, search modes,
  stock detail, inline historical chart, stats, recommendation, forecast, and
  loading/error/empty states.
- Added the lazy `indian-market` route and navigation entry in
  `frontend/src/app/router.tsx` and `frontend/src/app/layout/AppLayout.tsx`.
- Reused the typed endpoint wrappers and React Query hooks added earlier in
  Phase 3; no provider secret is included in frontend configuration.
- Validation passed: frontend typecheck, lint, production Vite/PWA build, and
  the Python test suite.

### Known limitation

The upstream API response subtrees are intentionally rendered defensively
until live sanitized fixtures confirm field names for every overview and
analytical payload. The next provider rollout phase should promote stable
fields into typed presentation models and add fixture-backed frontend tests.

## Update – Indian Market workspace completion (2026-07-31)

- Added debounced company, industry, and mutual-fund discovery so provider
  quota is not consumed for every keystroke.
- Added explicit empty-search results, disabled open behavior, and selection
  of provider identifiers from discovery results.
- Surfaced overview warnings and stale metadata, plus loading/error states for
  recommendation and forecast panels.
- Revalidated the frontend with the strict ESLint command and production
  TypeScript/Vite/PWA build.

### Final status

Phase 2 backend/API foundation and the Phase 3 React workspace are complete.
Yahoo Finance remains unchanged as the primary market-data provider.

## Update – Phase 4 rollout readiness (2026-07-31)

### Completed code-owned rollout work

- Added deployment-managed `auth_header` and `auth_scheme` settings so the
  provider's authentication convention can be configured without code edits.
- Added redacted `IndianApiTelemetry` counters for requests, cache hits,
  successes, errors, rate limits, latency, and the last HTTP/error status.
- Added Product Owner-only `GET /api/indian-market/status`; it reports enablement,
  configuration presence, provider selection, and telemetry without returning
  the API key or upstream data.
- Added `scripts/smoke_indian_api.py`, a manual live check that is excluded from
  CI and prints only pass/fail names plus sanitized telemetry.
- Added Render environment entries for the feature flag, base URL, API key,
  authentication header, and optional scheme. The flag remains disabled by
  default.

### Phase 4 runbook

1. Confirm the provider's official base URL, authentication header/scheme,
   terms, quota, and caching/redistribution rules.
2. Set the five Indian API variables in a disposable Render preview, leaving
   `SCREENER_INDIAN_API_ENABLED=false` while validating configuration.
3. Enable the flag and run `python scripts/smoke_indian_api.py --stock RELIANCE`
   during both open and closed-market windows. Do not run this in CI.
4. Review Product Owner status at `/api/indian-market/status` for latency,
   error, and rate-limit counters; capture sanitized fixtures and compatibility
   decisions for each endpoint.
5. Keep `SCREENER_MARKET_DATA_PROVIDER=yahoo` until endpoint compatibility and
   reliability are approved. Only then decide whether a separate, explicitly
   configured hybrid capability should be introduced.

### Current Phase 4 status

The repository is rollout-ready, but live activation is intentionally blocked
until a real provider key, official auth convention, and terms confirmation are
available. No live provider call was made from this development environment.
