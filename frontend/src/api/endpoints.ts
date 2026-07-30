import { http } from "./client";
import type {
  AuthToken,
  BrokerConnectRequest,
  BrokerInstructionsResponse,
  BrokerStatusResponse,
  FiltersResponse,
  HoldingsResponse,
  KnowledgeResponse,
  LearnResult,
  ScanRequest,
  ScanResponse,
  ScanRow,
  SearchResponse,
  Settings,
  SettingsPatch,
  UserProfile,
  VerifyResponse,
  WatchlistResponse,
} from "@/types/api";

/** Typed wrappers around every backend endpoint (see api.py). */
export const api = {
  /* Auth */
  register: (body: { username: string; password: string; display_name?: string }) =>
    http.post<AuthToken>("/api/auth/register", body),
  login: (body: { username: string; password: string }) =>
    http.post<AuthToken>("/api/auth/login", body),
  logout: () => http.post<{ message: string }>("/api/auth/logout"),
  me: () => http.get<UserProfile>("/api/auth/me"),

  /* Preferences (per-user settings) */
  preferences: () => http.get<Settings>("/api/preferences"),
  updatePreferences: (patch: SettingsPatch) =>
    http.post<Record<string, unknown>>("/api/preferences", { patch }),
  resetPreferences: () => http.post<Record<string, unknown>>("/api/preferences/reset"),
  watchlist: () => http.get<WatchlistResponse>("/api/preferences/watchlist"),
  setWatchlist: (symbols: string[]) =>
    http.post<WatchlistResponse>("/api/preferences/watchlist", { symbols }),

  /* Analysis */
  recommend: (symbol: string) =>
    http.get<ScanRow>(`/api/recommend/${encodeURIComponent(symbol)}`),
  scan: (body: ScanRequest) => http.post<ScanResponse>("/api/scan", body),
  filters: () => http.get<FiltersResponse>("/api/filters"),
  search: (q: string) => http.get<SearchResponse>(`/api/search?q=${encodeURIComponent(q)}`),
  verify: () => http.get<VerifyResponse>("/api/verify"),

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
};
