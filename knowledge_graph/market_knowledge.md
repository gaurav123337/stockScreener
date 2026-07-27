# Stock Market Knowledge Base (Indian Market — NSE/BSE)
> Last reviewed: 2026-07. This file is the screener's "brain".
> The `learn` command ingests PDFs/notes from the `knowledge/` folder and appends
> distilled rules here, so the system stays updated with market trends.

## 1. How the market works (core mechanics)
- Stocks trade on exchanges (NSE/BSE). Price = last matched buy/sell. Driven by
  supply/demand, which is driven by earnings expectations, news, macro (rates,
  inflation, RBI policy), FII/DII flows, and sentiment.
- Long-term prices follow **earnings & cash flows**; short-term prices follow
  **sentiment, liquidity and momentum**.
- Circuit filters (5/10/20%) limit daily moves; avoid chasing stocks near circuits.
- Settlement is T+1 in India since 2024.

## 2. Trend & momentum (technical)
- **Trend**: price above rising 50-DMA and 200-DMA = uptrend. "Golden cross"
  (50 > 200) is bullish; "death cross" is bearish.
- **RSI(14)**: >70 overbought (risk of pullback), <30 oversold (possible bounce),
  40–60 neutral. Buy-the-dip in an uptrend when RSI cools to 40–50.
- **MACD**: MACD line crossing above signal = bullish momentum shift; below = bearish.
- **52-week high/low**: near 52w high + strong trend = momentum strength;
  near 52w low = either value opportunity or falling knife (check fundamentals).
- **Volume**: breakouts on >1.5x average volume are more reliable.

## 3. Fundamentals & valuation
- **P/E**: price per unit of earnings. Compare to sector & history, not in isolation.
  High P/E needs high growth to justify (see PEG).
- **PEG = P/E ÷ earnings growth %**. PEG < 1 ≈ undervalued vs growth; > 2 expensive.
- **P/B**: matters for banks/NBFCs & asset-heavy firms. Low P/B can be value or a trap.
- **ROE / ROCE**: >15% consistently = quality. Compare with cost of capital.
- **Debt/Equity**: <1 preferred (lower for non-financials). High debt + falling rates
  can help; high debt + rising rates is risky.
- **Profit & revenue growth**: look for consistent multi-year growth.
- **Free cash flow**: positive & growing FCF = healthy.

## 4. Buy / Sell framework (how signals are generated)
A recommendation combines **Trend + Momentum + Valuation + Quality + Risk**:
- **BUY**: uptrend (price > 50DMA & 200DMA) + momentum turning up (MACD cross or
  RSI rising from 40–55) + reasonable valuation (PEG not extreme) + decent quality
  (ROE, manageable debt). Entry near support (50DMA or recent swing low).
  - **Target price**: recent resistance / 52w high, or entry × (1 + expected move).
  - **Stop-loss**: below 50DMA or recent swing low (risk ~5–8%).
- **SELL / AVOID**: downtrend (price < falling 200DMA), MACD cross down, RSI
  breaking below 40, or valuation stretched with growth slowing. Book profits near
  resistance when momentum weakens.
- **HOLD/WATCH**: mixed signals — wait for confirmation.

## 5. Risk management (non-negotiable)
- Never risk >1–2% of capital on a single trade (position sizing).
- Always define stop-loss **before** entry. Risk:Reward ≥ 1:2 preferred.
- Diversify across sectors; avoid concentrated bets.
- This tool is educational, **not SEBI-registered investment advice**.

## 6. Learned rules (auto-appended by `learn` command)
<!-- New distilled insights from PDFs/notes get appended below this line. -->

### From `sample_notes.md`
- - When RSI falls below 30 in an uptrend that holds above the 200-DMA, it often marks a low-risk buying zone.
- - A breakout above a 52-week high on volume greater than 1.5x the 20-day average tends to follow through.
- - Avoid buying when PEG is above 2 and earnings growth is slowing; the trend can reverse sharply.
- - Always place a stop-loss below the 50-DMA or recent swing low before entering a momentum trade.
- - Banks and NBFCs are best compared on price-to-book and ROE rather than P/E alone.

### From `test_transcript.txt`
- ﻿RSI below 30 in an uptrend often marks a buying zone.
- Always use a stop-loss below the 50-DMA before entering momentum trades.
- Avoid PEG above 2 with slowing earnings growth.

### From `url_https_example_com_great_article.md`
- RSI below 30 signals oversold.
- Always set a stop-loss near the 50-DMA before entering.
