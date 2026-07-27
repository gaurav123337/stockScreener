# stockScreener (Indian Market — NSE/BSE)

Screens Indian stocks and tells you **when to buy/sell, at what price, and why** —
with pre-defined + custom filters, a self-updating knowledge base (PDFs/notes/URLs/
video transcripts), optional broker APIs (Zerodha/Angel One), and a self-verification
loop. Available both as a **mobile-installable web app (PWA)** and a **CLI**.

> ⚠️ Educational tool. **Not SEBI-registered investment advice.** Do your own research.

## Install
```bash
pip install -r requirements.txt
```

## 🌐 Web App (SPA · installable on mobile)
```bash
python api.py            # serves on http://localhost:8000
```
Open **http://localhost:8000** in a browser. It's a single-page app with 5 tabs:
- **Recommend** — type symbols → BUY/SELL/HOLD card with entry, target, stop-loss, R:R and reasons.
- **Scan** — screen Nifty 50 (or your list) with a pre-defined filter chip or a custom expression, ranked by score.
- **Train** — upload PDFs / notes / video transcripts, or paste a blog/article URL; it extracts market rules into the knowledge base. View the knowledge base here too.
- **Brokers** — connect **Zerodha Kite** or **Angel One SmartAPI** (step-by-step instructions in-app) for live LTP and your holdings/positions. Optional — the app works fine on free data.
- **Guide** — how to use everything.

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


## Commands

### 1) Recommend (buy/sell/hold + entry/target/stop-loss + reasons)
```bash
python main.py recommend RELIANCE TCS INFY
```
Shows for each stock: action (BUY/SELL/HOLD), score, last price, and for BUY/SELL
an **entry, target, stop-loss, risk:reward**, plus the **reasons** (trend vs
50/200-DMA, RSI, MACD, volume, PEG/ROE/debt).

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
Built-ins: `oversold`, `uptrend`, `value`, `quality`, `momentum`,
`near_52w_high`, `near_52w_low`, `buy_signals`, `sell_signals`.

Custom filter fields: `score, price, rsi, pe, peg, roe, debt_to_equity, sma50,
sma200, above_sma50, above_sma200, golden_cross, near_52w_high, near_52w_low`
with `and / or / not` and `< <= > >= == !=`.

### 4) Self-update from PDFs / notes (internet research, books, reports)
Drop any `.pdf`, `.md`, or `.txt` into the `knowledge/` folder, then:
```bash
python main.py learn
```
It extracts market-relevant rules and appends them to
`knowledge_graph/market_knowledge.md` (de-duplicated via a manifest).

### 5) Verify its own predictions
Every BUY/SELL call is logged to `data/predictions.csv`. After the 30-day
horizon, run:
```bash
python main.py verify
```
It re-fetches current prices and reports **hit-rate overall and by action**
(target_hit / correct / stop_hit / wrong), so you can judge reliability.

## How the recommendation works
Score = **Trend** (price vs 50/200-DMA, golden/death cross) + **Momentum**
(RSI, MACD cross) + **Volume** + **Fundamentals** (PEG, ROE, Debt/Equity).
- Score ≥ +30 → **BUY**; ≤ −30 → **SELL**; else **HOLD**.
- **Target** = nearer of 2×risk or 52-week high; **Stop-loss** = below 50-DMA or
  1.5×ATR (whichever is closer). Rules live in `knowledge_graph/market_knowledge.md`.

## Project layout
```
api.py                     # FastAPI backend (serves SPA + JSON APIs)  ->  python api.py
main.py                    # CLI
screener/
  data.py                  # yfinance fetch (ticker normalisation, retries)
  indicators.py            # SMA/EMA/RSI/MACD/ATR/52w
  signals.py               # recommendation engine (score -> BUY/SELL/HOLD)
  filters.py               # pre-defined + safe custom filters
  knowledge.py             # PDF/notes/URL/video-transcript ingestion -> KB
  verify.py                # self-verification of predictions
  brokers.py               # optional Zerodha / Angel One adapters
  universe.py              # Nifty 50 symbol list
web/                       # the SPA (PWA)
  index.html               # app shell (5 tabs)
  manifest.json            # PWA manifest (installable)
  sw.js                    # service worker (offline shell, network-first API)
  static/                  # app.js, styles.css, icon.svg
knowledge_graph/
  objective.md             # your goal
  market_knowledge.md      # the "brain" (rules the engine follows)
knowledge/                 # drop PDFs/notes/transcripts here, then `learn`
data/                      # predictions.csv + broker_settings.json (auto-created)
```


