import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/endpoints";
import { useAuth } from "@/features/auth/auth-context";

export function useEntitlements() {
  const { isLoggedIn } = useAuth();
  const query = useQuery({
    queryKey: ["billing", "entitlements"],
    queryFn: api.billingEntitlements,
    enabled: isLoggedIn,
    staleTime: 30_000,
  });
  return {
    entitlements: query.data ?? null,
    isPro: query.data?.is_pro ?? false,
    isFree: query.data ? !query.data.is_pro : false,
    isPending: query.isPending,
    isLoading: isLoggedIn && query.isPending,
    refetch: query.refetch,
  };
}
