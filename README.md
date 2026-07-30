# stockScreener (Indian Market — NSE/BSE)

Screens Indian stocks and tells you **when to buy/sell, at what price, and why** —
with pre-defined + custom filters, a self-updating knowledge base (PDFs/notes/URLs/
video transcripts), optional broker APIs (Zerodha/Angel One), and a self-verification
loop. Available both as a **mobile-installable web app (PWA)** and a **CLI**.

> ⚠️ Educational tool. **Not SEBI-registered investment advice.** Do your own research.

For a free, disposable early-testing deployment, follow [DEPLOYMENT.md](DEPLOYMENT.md).

---

## 🏗️ Architecture (v0.3.0)

The codebase has been refactored using **Clean Architecture** principles with a
**plugin system** for extensibility. It is now highly reusable and maintainable.

### Layers

```
┌─────────────────────────────────────────┐
│  Presentation  │  api.py (FastAPI)      │  ← Web routes, request/response
│                │  main.py (CLI)         │  ← Console output, Rich tables
├─────────────────────────────────────────┤
│  Services      │  AnalysisService       │  ← Business logic orchestration
│                │  ScanService           │
│                │  VerificationService   │
│                │  KnowledgeService      │
│                │  FilterService         │
│                │  BrokerService         │
├─────────────────────────────────────────┤
│  Core          │  models.py (Pydantic)  │  ← Domain models, validation
│                │  interfaces.py (ABC)   │  ← Contracts / ports
│                │  config.py (Settings)  │  ← Centralized configuration
│                │  container.py (DI)     │  ← Dependency injection
│                │  plugins.py (Registry) │  ← Plugin registry
├─────────────────────────────────────────┤
│  Infrastructure                        │  ← External world adapters
│                │  YahooDataProvider     │  ← MarketDataProvider impl
│                │  CSVPredictionRepo     │  ← PredictionRepository impl
│                │  MarkdownKnowledgeStore│  ← KnowledgeStore impl
│                │  ZerodhaAdapter        │  ← BrokerAdapter impl
│                │  AngelOneAdapter       │  ← BrokerAdapter impl
└─────────────────────────────────────────┘
```

### Key Patterns

| Pattern | Where | Benefit |
|---------|-------|---------|
| **Dependency Injection** | `core/container.py` | Testable, swappable implementations |
| **Plugin Registry** | `core/plugins.py` | Add filters/scorers/brokers without modifying core |
| **Repository** | `infrastructure/persistence/` | Abstract data storage (CSV → DB later) |
| **Strategy** | `services/scoring_engine.py` | Pluggable scoring algorithms |
| **Service Layer** | `services/` | Single place for business logic (no duplication) |
| **Configuration** | `core/config.py` | Environment-aware, validated settings |

### Project Layout

```
api.py                          # FastAPI backend (serves SPA + JSON APIs)
main.py                         # CLI
screener/
  bootstrap.py                  # Wires all DI dependencies at startup
  __init__.py
  core/                         # Framework (no business logic)
    config.py                   # Pydantic Settings — all config in one place
    models.py                   # Pydantic domain models (validated, serializable)
    interfaces.py               # Abstract base classes (ports)
    container.py                # Lightweight DI container
    plugins.py                  # Plugin registry for filters/scorers/brokers
  infrastructure/               # Adapters to external world
    data/yahoo_provider.py      # Yahoo Finance implementation
    persistence/csv_repository.py # CSV/MD file storage
  services/                     # Business logic orchestration
    analysis_service.py         # Stock analysis (replaces duplicated logic)
    scan_service.py             # Universe scanning
    verification_service.py     # Prediction logging & verification
    knowledge_service.py        # PDF/URL ingestion
    filter_service.py           # Predefined + custom expression filters
    broker_service.py           # Broker management (Zerodha, Angel One)
    scoring_engine.py           # Pluggable scoring strategies
  indicators.py                 # Technical indicators (unchanged)
  universe.py                   # Nifty 50 symbol list (unchanged)
frontend/                       # React 18 + Vite + TypeScript SPA (PWA)
  src/
    api/                        # Typed API client + endpoint wrappers
    app/                        # Shell: layout, router, toast, query client
    features/                   # One module per tab (recommend, scan, train, ...)
    components/                 # Shared UI (Section, RecommendationCard)
    types/api.ts                # Types mirroring the FastAPI JSON payloads
  dist/                         # Production build (served by api.py)
web/                            # Legacy vanilla SPA — fallback if no build exists
  index.html
  manifest.json
  sw.js
  static/                       # app.js, styles.css, icon.svg
knowledge_graph/
  objective.md
  market_knowledge.md           # The "brain" (rules the engine follows)
knowledge/                      # Drop PDFs/notes/transcripts here
tests/
  test_engine.py                # Offline tests with mocks
data/                           # predictions.csv + broker_settings.json
```

---

## Install

```bash
pip install -r requirements.txt
```

## 🌐 Web App (SPA · installable on mobile)

```bash
python api.py            # serves on http://localhost:8000
```

Open **http://localhost:8000** in a browser. It's a single-page app with 6 tabs:
- **Recommend** — type symbols → BUY/SELL/HOLD card with entry, target, stop-loss, R:R and reasons.
- **Scan** — screen Nifty 50 (or your list) with a pre-defined filter chip or a custom expression, ranked by score.
- **Train** — upload PDFs / notes / video transcripts, or paste a blog/article URL; it extracts market rules into the knowledge base. View the knowledge base here too.
- **Brokers** — connect **Zerodha Kite** or **Angel One SmartAPI** (step-by-step instructions in-app) for live LTP and your holdings/positions. Optional — the app works fine on free data.
- **Guide** — how to use everything.

### ⚛️ Frontend development (React + Vite + TypeScript)

The SPA lives in `frontend/` and is a React 18 + Vite + TypeScript app
(TanStack Query, React Router, React Hook Form, CSS Modules, `vite-plugin-pwa`).
`api.py` serves the production build from `frontend/dist/` when present and
falls back to the legacy vanilla SPA in `web/` otherwise.

```bash
cd frontend
npm install          # one-time
npm run dev          # dev server on :5173, proxies /api → :8000 (run api.py too)
npm run build        # type-check + production build → frontend/dist
npm run lint         # ESLint (zero warnings allowed)
npm run typecheck    # tsc --noEmit
```

Workflow: run `python api.py` in one terminal and `npm run dev` in another for
hot-reload development; `npm run build` before deploying so `api.py` serves the
fresh bundle.

### 📲 Install on your phone (PWA)
It's a Progressive Web App (manifest + service worker), so it installs like a native app:
- **Android (Chrome):** tap the **Install** button at the top, or menu → *Add to Home screen*.
- **iPhone (Safari):** tap **Share** → *Add to Home Screen*.
- Your phone must reach the server: same Wi-Fi (`http://<your-PC-IP>:8000`), or host it online over **HTTPS** to install anywhere.

## 🧠 Training / self-update
- Upload **PDF**, **.md**, **.txt**, or a **video transcript** (`.txt`/`.srt`/`.vtt`) via the Train tab (or drop files into `knowledge/` and run `python main.py learn`).
- Paste a **URL** of a blog/article to ingest it.
- Rules are appended to `knowledge_graph/market_knowledge.md` (de-duplicated via a manifest).

## 🔌 Broker APIs (optional, better results)

| Broker | Library | Notes |
|---|---|---|
| Zerodha Kite Connect | `pip install kiteconnect` | Daily login → access_token (expires each day). |
| Angel One SmartAPI | `pip install smartapi-python pyotp` | client_code + PIN + TOTP secret. |

Connect in the **Brokers** tab. Once connected, recommendations use **live broker LTP** and you can pull **holdings/positions**. If not connected, everything still works on free Yahoo data.

---

## Commands

### 1) Recommend (buy/sell/hold + entry/target/stop-loss + reasons)
```bash
python main.py recommend RELIANCE TCS INFY
```

### 2) Scan a universe (default = Nifty 50)
```bash
python main.py scan                          # all, ranked by score
python main.py scan --top 10                 # top 10 by score
python main.py scan --filter momentum        # pre-defined filter
python main.py scan --where "rsi < 35 and roe > 0.15"   # custom filter
python main.py scan --symbols RELIANCE TCS SBIN --filter buy_signals
```

### 3) List pre-defined filters
```bash
python main.py filters
```

### 4) Self-update from PDFs / notes
```bash
python main.py learn
```

### 5) Verify its own predictions
```bash
python main.py verify
```

---

## How the recommendation works

Score = **Trend** (price vs 50/200-DMA, golden/death cross) + **Momentum**
(RSI, MACD cross) + **Volume** + **Fundamentals** (PEG, ROE, Debt/Equity).
- Score ≥ +30 → **BUY**; ≤ −30 → **SELL**; else **HOLD**.
- **Target** = nearer of 2×risk or 52-week high; **Stop-loss** = below 50-DMA or
  1.5×ATR (whichever is closer). Rules live in `knowledge_graph/market_knowledge.md`.

---

## 🔧 Extending the Framework

### Adding a new scoring strategy

```python
from screener.core.interfaces import ScoringStrategy
from screener.core.plugins import registry

class MyScorer(ScoringStrategy):
    @property
    def name(self):
        return "my_scorer"

    def score(self, last, prev, info):
        if last.get("RSI14", 50) < 25:
            return 15.0, ["Extreme oversold — high bounce probability"]
        return 0.0, []

registry.register_scorer(MyScorer())
```

### Adding a new filter

```python
from screener.core.interfaces import FilterStrategy
from screener.core.plugins import registry

class MyFilter(FilterStrategy):
    @property
    def name(self):
        return "my_filter"

    @property
    def description(self):
        return "My custom screen"

    def matches(self, row):
        return row.get("rsi", 50) < 25 and row.get("score", 0) > 40

registry.register_filter(MyFilter())
```

### Adding a new broker

```python
from screener.core.interfaces import BrokerAdapter
from screener.core.plugins import registry

class MyBroker(BrokerAdapter):
    @property
    def name(self):
        return "mybroker"

    # Implement is_connected, status, get_ltp, get_holdings, connect, disconnect
    ...

registry.register_broker(MyBroker())
```

### Swapping data providers (e.g., for testing)

```python
from screener.core.container import container
from screener.core.interfaces import MarketDataProvider
from mymodule import MyDataProvider

container.register(MarketDataProvider, MyDataProvider)
```

---

## Environment Variables

All configuration can be overridden via environment variables with the `SCREENER_` prefix:

```bash
# Scoring thresholds
SCREENER_SCORE_BUY_THRESHOLD=35
SCREENER_SCORE_SELL_THRESHOLD=-35

# Data fetching
SCREENER_DATA_DEFAULT_PERIOD=2y
SCREENER_DATA_MAX_WORKERS=12

# Risk management
SCREENER_RISK_ATR_MULTIPLIER=2.0
SCREENER_RISK_RISK_REWARD_TARGET=2.5

# Verification
SCREENER_VERIFY_HORIZON_DAYS=45
```

---

## Testing

```bash
python tests/test_engine.py
```

Tests use **mock data providers** so they run offline without hitting Yahoo Finance.

---

## Migration from v0.2.0

- `screener/data.py` → `screener/infrastructure/data/yahoo_provider.py` (implements `MarketDataProvider`)
- `screener/signals.py` → `screener/services/analysis_service.py` + `screener/services/scoring_engine.py`
- `screener/filters.py` → `screener/services/filter_service.py` (plugin-based)
- `screener/knowledge.py` → `screener/services/knowledge_service.py` + `screener/infrastructure/persistence/csv_repository.py`
- `screener/verify.py` → `screener/services/verification_service.py` + `screener/infrastructure/persistence/csv_repository.py`
- `screener/brokers.py` → `screener/services/broker_service.py` (adapter pattern)

The old modules are kept for backward compatibility but are no longer used by the main entry points.
