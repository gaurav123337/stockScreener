import type {
  AdminFeedback,
  AdminFeedbackDetail,
  AdminOverview,
  AdminUser,
  AuditEvent,
  AuthToken,
  BrokerConnectRequest,
  BrokerInstructionsResponse,
  BrokerStatusResponse,
  ComplianceResponse,
  ConfigDiff,
  ConfigPublication,
  ConfigRegistryItem,
  FeedbackReceipt,
  FeedbackRequest,
  FiltersResponse,
  HoldingsResponse,
  IndianEnvelope,
  IndianHistory,
  IndianOverview,
  IndianSearchResult,
  IndianStats,
  IndianStock,
  KnowledgeResponse,
  LearnResult,
  Paginated,
  ScanRequest,
  ScanResponse,
  ScanRow,
  SearchResponse,
  Settings,
  SettingsPatch,
  UserProfile,
  VerifyResponse,
  BacktestReport,
  WatchlistResponse,
} from "@/types/api";
import { http } from "./client";

/** Typed wrappers around every backend endpoint (see api.py). */
export const api = {
  /* Auth */
  register: (body: {
    email: string;
    password: string;
    password_confirmation: string;
    display_name?: string;
  }) => http.post<AuthToken>("/api/auth/register", body),
  login: (body: { email: string; password: string }) =>
    http.post<AuthToken>("/api/auth/login", body),
  logout: () => http.post<{ message: string }>("/api/auth/logout"),
  logoutAll: () => http.post<{ message: string }>("/api/auth/logout-all"),
  verifyEmail: (token: string) => http.post<UserProfile>("/api/auth/verify-email", { token }),
  resendVerification: () => http.post<{ message: string }>("/api/auth/resend-verification"),
  forgotPassword: (email: string) =>
    http.post<{ message: string }>("/api/auth/forgot-password", { email }),
  resetPassword: (token: string, password: string, passwordConfirmation: string) =>
    http.post<{ message: string }>("/api/auth/reset-password", {
      token,
      password,
      password_confirmation: passwordConfirmation,
    }),
  me: () => http.get<UserProfile>("/api/auth/me"),

  /* Product owner control center */
  adminOverview: () => http.get<AdminOverview>("/api/admin/overview"),
  adminUsers: (query = "") =>
    http.get<Paginated<AdminUser>>(`/api/admin/users${query ? `?${query}` : ""}`),
  adminUser: (userId: string) =>
    http.get<AdminUser>(`/api/admin/users/${encodeURIComponent(userId)}`),
  setAdminUserStatus: (userId: string, status: string, reason: string) =>
    http.post<AdminUser>(`/api/admin/users/${encodeURIComponent(userId)}/status`, {
      status,
      reason,
    }),
  sendAdminPasswordReset: (userId: string, reason: string) =>
    http.post<{ message: string }>(
      `/api/admin/users/${encodeURIComponent(userId)}/password-reset`,
      { reason },
    ),
  adminFeedback: (query = "") =>
    http.get<Paginated<AdminFeedback>>(`/api/admin/feedback${query ? `?${query}` : ""}`),
  adminFeedbackDetail: (feedbackId: string) =>
    http.get<AdminFeedbackDetail>(`/api/admin/feedback/${encodeURIComponent(feedbackId)}`),
  updateAdminFeedback: (feedbackId: string, body: Record<string, unknown>) =>
    http.post<AdminFeedback>(`/api/admin/feedback/${encodeURIComponent(feedbackId)}`, body),
  configRegistry: () => http.get<{ items: ConfigRegistryItem[] }>("/api/admin/config/registry"),
  currentGlobalConfig: () => http.get<ConfigPublication>("/api/admin/config/current"),
  validateGlobalConfig: (patch: SettingsPatch) =>
    http.post<{ valid: boolean; values: Settings }>("/api/admin/config/validate", { patch }),
  diffGlobalConfig: (patch: SettingsPatch) =>
    http.post<ConfigDiff>("/api/admin/config/diff", { patch }),
  globalConfigHistory: () => http.get<{ items: ConfigPublication[] }>("/api/admin/config/history"),
  publishGlobalConfig: (
    patch: SettingsPatch,
    policies: Record<string, string>,
    reason: string,
    expectedVersion: number,
  ) =>
    http.post<ConfigPublication>("/api/admin/config/publish", {
      patch,
      policies,
      reason,
      expected_version: expectedVersion,
    }),
  rollbackGlobalConfig: (version: number, reason: string) =>
    http.post<ConfigPublication>("/api/admin/config/rollback", { version, reason }),
  adminAudit: () => http.get<{ items: AuditEvent[] }>("/api/admin/audit"),

  /* Tester feedback */
  submitFeedback: (body: FeedbackRequest) => http.post<FeedbackReceipt>("/api/feedback", body),

  /* Preferences (per-user settings) */
  preferences: () => http.get<Settings>("/api/preferences"),
  updatePreferences: (patch: SettingsPatch) =>
    http.post<Record<string, unknown>>("/api/preferences", { patch }),
  resetPreferences: () => http.post<Record<string, unknown>>("/api/preferences/reset"),
  watchlist: () => http.get<WatchlistResponse>("/api/preferences/watchlist"),
  setWatchlist: (symbols: string[]) =>
    http.post<WatchlistResponse>("/api/preferences/watchlist", { symbols }),

  /* Analysis */
  recommend: (symbol: string) => http.get<ScanRow>(`/api/recommend/${encodeURIComponent(symbol)}`),
  scan: (body: ScanRequest) => http.post<ScanResponse>("/api/scan", body),
  filters: () => http.get<FiltersResponse>("/api/filters"),
  search: (q: string) => http.get<SearchResponse>(`/api/search?q=${encodeURIComponent(q)}`),
  verify: () => http.get<VerifyResponse>("/api/verify"),
  backtest: () => http.get<BacktestReport>("/api/backtest"),
  backtestRun: () => http.post<BacktestReport>("/api/backtest/run"),
  compliance: () => http.get<ComplianceResponse>("/api/compliance"),

  /* Settings */
  settings: () => http.get<Settings>("/api/settings"),
  settingsDefaults: () => http.get<Settings>("/api/settings/defaults"),
  updateSettings: (patch: SettingsPatch) =>
    http.post<Record<string, unknown>>("/api/settings", { patch }),
  resetSettings: () => http.post<Record<string, unknown>>("/api/settings/reset"),

  /* Knowledge / training */
  learnFile: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return http.postForm<LearnResult>("/api/learn/file", form);
  },
  learnUrl: (url: string) => http.post<LearnResult>("/api/learn/url", { url }),
  learnNow: () => http.post<LearnResult>("/api/learn"),
  knowledge: () => http.get<KnowledgeResponse>("/api/knowledge"),

  /* Brokers */
  brokerInstructions: () => http.get<BrokerInstructionsResponse>("/api/brokers/instructions"),
  brokerStatus: () => http.get<BrokerStatusResponse>("/api/brokers/status"),
  brokerConnect: (body: BrokerConnectRequest) =>
    http.post<Record<string, unknown>>("/api/brokers/connect", body),
  brokerDisconnect: (broker: string) =>
    http.post<Record<string, unknown>>(`/api/brokers/disconnect/${encodeURIComponent(broker)}`),
  brokerHoldings: () => http.get<HoldingsResponse>("/api/brokers/holdings"),

  /* Optional Indian market workspace (credentials stay server-side). */
  indianStock: (query: string) =>
    http.get<IndianEnvelope<IndianStock>>(
      `/api/indian-market/stock?q=${encodeURIComponent(query)}`,
    ),
  indianIndustrySearch: (query: string) =>
    http.get<IndianEnvelope<IndianSearchResult[]>>(
      `/api/indian-market/industry-search?q=${encodeURIComponent(query)}`,
    ),
  indianMutualFundSearch: (query: string) =>
    http.get<IndianEnvelope<IndianSearchResult[]>>(
      `/api/indian-market/mutual-funds/search?q=${encodeURIComponent(query)}`,
    ),
  indianOverview: () => http.get<IndianEnvelope<IndianOverview>>("/api/indian-market/overview"),
  indianHistory: (stockId: string, period = "", filter = "") => {
    const params = new URLSearchParams();
    if (period) params.set("period", period);
    if (filter) params.set("filter", filter);
    return http.get<IndianEnvelope<IndianHistory>>(
      `/api/indian-market/stock/${encodeURIComponent(stockId)}/history${params.size ? `?${params}` : ""}`,
    );
  },
  indianStats: (stockId: string, stats = "") =>
    http.get<IndianEnvelope<IndianStats>>(
      `/api/indian-market/stock/${encodeURIComponent(stockId)}/stats${stats ? `?stats=${encodeURIComponent(stats)}` : ""}`,
    ),
  indianRecommendations: (stockId: string) =>
    http.get<IndianEnvelope<unknown>>(
      `/api/indian-market/stock/${encodeURIComponent(stockId)}/recommendations`,
    ),
  indianForecasts: (stockId: string, params: Record<string, string> = {}) => {
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => Boolean(value)));
    return http.get<IndianEnvelope<unknown>>(
      `/api/indian-market/stock/${encodeURIComponent(stockId)}/forecasts${query.size ? `?${query}` : ""}`,
    );
  },
};
