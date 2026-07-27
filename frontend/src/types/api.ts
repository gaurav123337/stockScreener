/**
 * Domain types mirroring the FastAPI JSON payloads in api.py.
 * Keep in sync with screener/services response shapes (e.g. `to_scan_row()`).
 */

export type Action = "BUY" | "SELL" | "HOLD";

/** Row shape returned by /api/recommend/{symbol} and inside /api/scan results. */
export interface ScanRow {
  symbol: string;
  name: string | null;
  sector: string | null;
  action: Action;
  score: number;
  price: number | null;
  entry: number | null;
  target: number | null;
  stop_loss: number | null;
  rr: number | null;
  rsi: number | null;
  sma50: number | null;
  sma200: number | null;
  pe: number | null;
  peg: number | null;
  roe: number | null;
  reasons: string[] | null;
  error?: string | null;
}

export interface ScanRequest {
  symbols?: string[] | null;
  filter?: string | null;
  where?: string | null;
  top?: number | null;
}

export interface ScanResponse {
  count: number;
  failed: string[];
  results: ScanRow[];
}

export interface PredefinedFilter {
  name: string;
  desc: string;
}

export interface FiltersResponse {
  predefined: PredefinedFilter[];
  fields: Record<string, unknown> | string[];
}

export interface SearchResult {
  symbol: string;
  name: string;
  exchange: string;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
}

/* ---------------------------------- Settings --------------------------------- */

/** A settings section is a flat map of key -> number | string | string[]. */
export type SettingsSection = Record<string, number | string | string[]>;

export interface Settings {
  scoring: SettingsSection;
  risk: SettingsSection;
  data: SettingsSection;
  knowledge: SettingsSection;
  verification: SettingsSection;
  default_universe: string[];
  [section: string]: SettingsSection | string[];
}

export type SettingsPatch = Record<string, unknown>;

export interface SettingsUpdateRequest {
  patch: SettingsPatch;
}

/* ---------------------------------- Learning --------------------------------- */

export interface LearnResult {
  ok?: boolean;
  rules_added?: number;
  saved_as?: string;
  error?: string;
}

export interface KnowledgeResponse {
  path: string;
  content: string;
}

/* ---------------------------------- Brokers ---------------------------------- */

export interface BrokerInstruction {
  name: string;
  library: string;
  steps: string[];
  fields: string[];
}

export interface BrokerStatus {
  connected: boolean;
  library_installed: boolean;
  [key: string]: unknown;
}

export type BrokerInstructionsResponse = Record<string, BrokerInstruction>;
export type BrokerStatusResponse = Record<string, BrokerStatus>;

export interface BrokerConnectRequest {
  broker: string;
  credentials: Record<string, string>;
}

/** Holdings payload is broker-specific; treated as opaque JSON. */
export type HoldingsResponse = Record<string, unknown>;

/* ---------------------------------- Verification ----------------------------- */

export interface VerifyResponse {
  [key: string]: unknown;
}
