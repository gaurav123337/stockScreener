import { useQuery } from "@tanstack/react-query";
import { Database } from "lucide-react";
import { api } from "@/api/endpoints";
import { useAuth } from "@/features/auth/auth-context";
import { cn } from "@/lib/cn";

/**
 * Global "data comes from X" badge, rendered on every page by the app shell.
 * Visibility is controlled by the product owner via the control-center config
 * (`show_data_source`); when disabled, nothing is rendered at all.
 */
export function DataSourceBadge({ className }: { className?: string }) {
  const { isLoggedIn } = useAuth();
  const query = useQuery({
    queryKey: ["data-source"],
    queryFn: api.dataSource,
    enabled: isLoggedIn,
    staleTime: 60_000,
  });

  if (!isLoggedIn || !query.data?.show || !query.data.label) {
    return null;
  }

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full bg-surface-raised px-2.5 py-1 text-[11px] font-semibold text-muted",
        className,
      )}
      title="Market data provider"
    >
      <Database className="size-3 shrink-0" aria-hidden />
      <span>Data: {query.data.label}</span>
    </span>
  );
}
