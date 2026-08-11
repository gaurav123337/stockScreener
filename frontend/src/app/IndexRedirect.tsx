import { useQuery } from "@tanstack/react-query";
import { Navigate } from "react-router-dom";
import { api } from "@/api/endpoints";
import { LoadingState } from "@/components/ui/Spinner";
import { useAuth } from "@/features/auth/auth-context";

/**
 * Land the app somewhere sensible:
 * - a signed-in user who hasn't answered the risk questionnaire goes straight
 *   to the 5-question onboarding (Phase-2 beginner flow);
 * - everyone else keeps the classic /recommend landing.
 */
export default function IndexRedirect() {
  const { user, isLoggedIn } = useAuth();
  const profileQuery = useQuery({
    queryKey: ["risk-profile"],
    queryFn: api.getRiskProfile,
    enabled: isLoggedIn,
    staleTime: 5 * 60_000,
  });

  if (isLoggedIn && user?.role !== "product_owner" && profileQuery.isLoading) {
    return <LoadingState />;
  }

  const needsOnboarding =
    isLoggedIn &&
    user?.role !== "product_owner" &&
    profileQuery.data !== undefined &&
    !profileQuery.data.level;

  return <Navigate to={needsOnboarding ? "/onboarding" : "/recommend"} replace />;
}
