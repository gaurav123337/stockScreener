import type { PredefinedFilter } from "@/types/api";

/**
 * Built-in filter metadata mirrors FilterService defaults.
 * It keeps the scan controls useful while the API metadata request is loading
 * or temporarily unavailable; a successful API response remains authoritative.
 */
export const BUILT_IN_FILTERS: PredefinedFilter[] = [
  {
    name: "stable_companies",
    description: "Solid, low-debt companies that are still trending up",
    guided: true,
  },
  {
    name: "tax_saving",
    description: "Quality large companies — the closest stock pick to a tax-saving fund",
    guided: true,
  },
  {
    name: "growth",
    description: "Companies growing steadily, with reasonable prices",
    guided: true,
  },
  { name: "oversold", description: "RSI < 30 - possibly oversold bounce candidates" },
  {
    name: "uptrend",
    description: "Price above 50 & 200 DMA with golden cross - strong uptrend",
  },
  {
    name: "value",
    description: "PEG < 1 (or low P/E vs growth) - undervalued vs growth",
  },
  { name: "quality", description: "ROE > 15% and Debt/Equity < 1 - quality businesses" },
  { name: "momentum", description: "Score >= 30 and RSI 55-70 - strong momentum buys" },
  { name: "near_52w_high", description: "Within 5% of 52-week high - breakout watch" },
  {
    name: "near_52w_low",
    description: "Within 5% of 52-week low - deep value / knife catch",
  },
  { name: "buy_signals", description: "Current action == BUY" },
  { name: "sell_signals", description: "Current action == SELL" },
];
