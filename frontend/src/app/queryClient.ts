import { QueryClient } from "@tanstack/react-query";

/** Central TanStack Query client with sane defaults for this app. */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});
