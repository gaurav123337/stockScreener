/** Section metadata and friendly labels for the Settings dashboard. */

export const SECTION_META: ReadonlyArray<readonly [string, string, string]> = [
  [
    "scoring",
    "Scoring & Signals",
    "How aggressively stocks are scored. Higher weights = that factor matters more.",
  ],
  ["risk", "Risk & Trade Levels", "Stop-loss / target calculation."],
  ["data", "Data Fetching", "History window and reliability for market data."],
  ["knowledge", "Knowledge Base", "How training documents are ingested."],
  ["verification", "Verification", "How signal hit-rates are measured."],
];

const LABELS: Record<string, string> = {
  buy_threshold: "BUY score threshold",
  sell_threshold: "SELL score threshold",
  trend_weight_sma50: "Weight: above 50-DMA",
  trend_weight_sma200: "Weight: above 200-DMA",
  trend_weight_cross: "Weight: golden/death cross",
  momentum_weight_rsi: "Weight: RSI momentum",
  momentum_weight_macd: "Weight: MACD",
  momentum_weight_crossover: "Weight: MACD crossover",
  volume_weight: "Weight: volume surge",
  fundamental_peg_weight: "Weight: PEG valuation",
  fundamental_roe_weight: "Weight: ROE quality",
  fundamental_debt_weight: "Weight: low debt",
  atr_multiplier: "ATR stop-loss multiplier",
  risk_reward_target: "Target risk:reward",
  sma50_stop_discount: "50-DMA stop discount",
  default_period: "History period",
  default_interval: "Candle interval",
  retry_attempts: "Retry attempts",
  retry_pause_seconds: "Retry pause (sec)",
  max_workers: "Parallel fetch workers",
  max_rules_per_doc: "Max rules / document",
  min_rule_length: "Min rule length",
  max_rule_length: "Max rule length",
  allowed_extensions: "Allowed file types",
  horizon_days: "Evaluate after (days)",
  default_universe: "Default scan universe (symbols)",
};

export function label(key: string): string {
  return LABELS[key] ?? key.replace(/_/g, " ");
}
