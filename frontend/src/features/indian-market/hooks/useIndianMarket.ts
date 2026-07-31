import { api } from "@/api/endpoints";
import { useQuery } from "@tanstack/react-query";

const enabled = (value: string) => value.trim().length > 0;

export function useIndianOverview() {
  return useQuery({
    queryKey: ["indian-market", "overview"],
    queryFn: api.indianOverview,
    staleTime: 60_000,
  });
}

export function useIndianStock(query: string) {
  return useQuery({
    queryKey: ["indian-market", "stock", query],
    queryFn: () => api.indianStock(query),
    enabled: enabled(query),
    staleTime: 60_000,
  });
}

export function useIndianSearch(query: string, mode: "industry" | "mutual-fund") {
  return useQuery({
    queryKey: ["indian-market", mode, query],
    queryFn: () =>
      mode === "industry" ? api.indianIndustrySearch(query) : api.indianMutualFundSearch(query),
    enabled: enabled(query),
    staleTime: 60_000,
  });
}

export function useIndianStockData(stockId: string, period: string, filter: string) {
  const base = { enabled: enabled(stockId), staleTime: 60_000 };
  return {
    history: useQuery({
      ...base,
      queryKey: ["indian-market", "history", stockId, period, filter],
      queryFn: () => api.indianHistory(stockId, period, filter),
    }),
    stats: useQuery({
      ...base,
      queryKey: ["indian-market", "stats", stockId],
      queryFn: () => api.indianStats(stockId),
    }),
    recommendations: useQuery({
      ...base,
      queryKey: ["indian-market", "recommendations", stockId],
      queryFn: () => api.indianRecommendations(stockId),
    }),
    forecasts: useQuery({
      ...base,
      queryKey: ["indian-market", "forecasts", stockId],
      queryFn: () => api.indianForecasts(stockId),
    }),
  };
}
