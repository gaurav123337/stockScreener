/**
 * Domain types mirroring the FastAPI JSON payloads in api.py.
 * Keep in sync with screener/services response shapes (e.g. `to_scan_row()`).
 */

export type Action = "BUY" | "SELL" | "HOLD";

/* ---------------------------------- Auth ------------------------------------ */

export interface UserProfile {
  user_id: string;
  username: string;
  email: string | null;
  display_name: string | null;
  role: "user" | "product_owner";
  status: "active" | "suspended";
  email_verified_at: string | null;
  created_at: string;
  last_login_at: string | null;
  preferences: Record<string, unknown>;
}

export interface AuthToken {
  token: string;
  user: UserProfile;
  expires_at: string;
}

export interface WatchlistResponse {
  symbols: string[];
}

/* -------------------------------- Feedback ---------------------------------- */

export type FeedbackCategory = "bug" | "concern" | "idea" | "other";

export interface FeedbackRequest {
  category: FeedbackCategory;
  title: string;
  document: Record<string, unknown>;
  plain_text: string;
}

export interface FeedbackReceipt {
  feedback_id: string;
  created_at: string;
  message: string;
}

export interface AdminFeedback {
  feedback_id: string;
  user_id: string;
  username: string;
  category: FeedbackCategory;
  title: string;
  plain_text: string;
  status: "new" | "triaged" | "planned" | "in_progress" | "resolved" | "closed";
  priority: "low" | "medium" | "high" | "critical";
  assignee_id: string | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
}

export interface FeedbackEvent {
  event_id: string;
  feedback_id: string;
  actor_id: string;
  event_type: string;
  changes: Record<string, unknown>;
  note: string | null;
  reason: string;
  created_at: string;
}

export interface AdminFeedbackDetail {
  feedback: AdminFeedback;
  events: FeedbackEvent[];
}

export type AdminUser = UserProfile;

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminOverview {
  users: {
    total: number;
    verified: number;
    active: number;
    new_7d: number;
    new_30d: number;
    by_status: Record<"active" | "suspended", number>;
    by_verification: Record<"verified" | "pending", number>;
  };
  feedback: {
    total: number;
    guest: number;
    open: number;
    critical: number;
    overdue: number;
    by_status: Record<string, number>;
    by_category: Record<FeedbackCategory, number>;
    by_priority: Record<string, number>;
    by_age: Record<"under_7d" | "7_to_30d" | "over_30d", number>;
  };
  recent_users: AdminUser[];
  recent_feedback: AdminFeedback[];
  recent_config_publications: ConfigPublication[];
}

export interface ConfigPublication {
  version: number;
  values: Settings;
  policies: Record<string, string>;
  actor_id?: string;
  reason?: string;
  created_at?: string;
}

export interface ConfigDiff {
  from_version: number;
  changes: Array<{ key: string; before: unknown; after: unknown }>;
  values: Settings;
}

export interface ConfigRegistryItem {
  key: string;
  section: string;
  label: string;
  type: string;
  default: unknown;
  sensitive: boolean;
  user_overridable: boolean;
}

export interface AuditEvent {
  event_id: string;
  actor_id: string;
  action: string;
  target_type: string;
  target_id: string;
  reason: string;
  changes: Record<string, unknown>;
  created_at: string;
}

/** Row shape returned by /api/recommend/{symbol} and inside /api/scan results. */
export interface ScanRow {
  symbol: string;
  name: string | null;
  sector: string | null;
  action: Action;
  score: number;
  /** Phase-1 transparency measure (0..1) — NOT a probability of profit. */
  confidence?: number | null;
  /** Per-pillar score breakdown (trend/momentum/volume/fundamentals). */
  pillars?: Record<string, number>;
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
  /* ---- Phase-2 thesis-card additions (plain language) ---- */
  risk_badge?: string | null;
  portfolio_role?: string | null;
  /** Suggested share of the equity sleeve (0..1); null = don't add yet. */
  allocation_size?: number | null;
  drivers?: DriverScore[];
  what_could_go_wrong?: string[];
  thesis?: string | null;
}

/** One plain-language driver on a thesis card. */
export interface DriverScore {
  key: "trend" | "momentum" | "value" | "quality";
  label: string;
  score: number;
  positive: boolean | null;
  plain: string;
  why: string[];
}

/* ------------------------- Onboarding / risk profile ----------------------- */

export interface RiskOption {
  value: string;
  label: string;
}

export interface RiskQuestion {
  id: string;
  question: string;
  options: RiskOption[];
}

export type RiskLevel = "conservative" | "moderate" | "aggressive";

export interface RiskProfile {
  level: RiskLevel;
  label: string;
  summary: string;
  asset_split: { equity_delivery: number; mutual_funds: number; liquid: number };
  expected_return_range: number[];
  answers: Record<string, string>;
  created_at?: string;
}

export interface RiskProfileResponse {
  level: RiskLevel | null;
  label?: string;
  summary?: string;
  asset_split?: RiskProfile["asset_split"];
  expected_return_range?: number[];
  answers?: Record<string, string>;
}

/* --------------------------------- Plan ------------------------------------ */

export interface PlanBasketItem {
  symbol: string;
  name: string | null;
  sector: string | null;
  role: string;
  weight: number;
  score: number;
  action: Action;
  price: number;
  plain: string;
  risk_badge: string | null;
  driver_highlights: string[];
}

export interface InvestmentPlan {
  risk_level: RiskLevel;
  risk_label: string;
  goal: string;
  monthly_amount: number;
  horizon_years: number;
  asset_split: RiskProfile["asset_split"];
  basket: PlanBasketItem[];
  mutual_funds: string[];
  expected_return_range: number[];
  conservative_return_range: number[];
  notes: string[];
  generated_at: string;
}

/* --------------------------------- Glossary -------------------------------- */

export interface GlossaryResponse {
  terms: Record<string, { term: string; plain: string }>;
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
  /** Phase-0 trust/freshness envelope (see api.py /api/scan). */
  universe_size: number;
  coverage: number;
  scanned_at: string;
  educational_note?: string;
  disclaimer?: string;
  data_source?: string;
  data_updated_at?: string | null;
  stale?: boolean;
}

/** Trust framing + data-source attribution (GET /api/compliance). */
export interface ComplianceResponse {
  educational_note: string;
  disclaimer: string;
  data_source: string;
  is_investment_advice: boolean;
  data_updated_at: string | null;
  stale: boolean;
}

export interface PredefinedFilter {
  name: string;
  description: string;
  /** Phase-2: guided beginner presets are flagged so the UI shows them first. */
  guided?: boolean;
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

/** A settings section is a flat map of editable primitive and list values. */
export type SettingsSection = Record<string, number | string | boolean | string[]>;

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

/** One evaluation horizon's aggregate stats (shared by verify + backtest). */
export interface HorizonStats {
  horizon_days: number;
  n: number;
  hit_rate: number | null;
  avg_return: number | null;
  avg_win: number | null;
  avg_loss: number | null;
  max_drawdown: number | null;
  benchmark_avg_return: number | null;
  vs_benchmark: number | null;
  by_action: Record<string, { n: number; hit_rate: number; avg_return: number }>;
}

export interface VerifyResponse {
  evaluated_now: number;
  total_evaluated: number;
  overall_hit_rate: number | null;
  by_action: Record<string, { n: number; hit_rate: number | null }>;
  horizons: HorizonStats[];
  benchmark_symbol: string | null;
  window_start: string | null;
  generated_at: string;
}

/** Published walk-forward track record (GET /api/backtest). */
export interface BacktestReport {
  status: string;
  generated_at: string;
  window_start: string;
  window_end: string;
  universe: string[];
  universe_size: number;
  horizons: HorizonStats[];
  methodology: string[];
  notes: string[];
}

/* ---------------------------- Indian market API ----------------------------- */

export interface IndianEnvelope<T> {
  data: T;
  provider: string;
  fetched_at: string;
  stale?: boolean;
  warnings?: string[];
}

export interface IndianStock {
  ticker_id: string;
  company_name?: string | null;
  industry?: string | null;
  current_price: Record<string, number>;
  percent_change?: number | null;
  year_high?: number | null;
  year_low?: number | null;
  raw?: Record<string, unknown>;
}

export type IndianRecord = Record<string, unknown>;
export type IndianSearchResult = IndianRecord;
export type IndianSnapshot = IndianRecord[] | IndianRecord | null;
export interface IndianOverview {
  snapshots: Record<string, IndianSnapshot>;
}
export interface IndianHistory {
  stock_id: string;
  points: IndianRecord[];
}
export interface IndianStats {
  stock_id: string;
  stats: unknown;
}
