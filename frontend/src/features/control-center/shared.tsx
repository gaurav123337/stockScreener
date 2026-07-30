import { ApiError } from "@/api/client";
import { Card } from "@/components/ui/Card";
import { LoaderCircle } from "lucide-react";
import type { ReactNode } from "react";

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-bold">{title}</h1>
        <p className="mt-1 text-sm text-muted">{description}</p>
      </div>
      {actions}
    </div>
  );
}

export function QueryState({
  loading,
  error,
  children,
}: {
  loading: boolean;
  error: unknown;
  children: ReactNode;
}) {
  if (loading)
    return (
      <div className="flex min-h-56 items-center justify-center text-muted">
        <LoaderCircle className="mr-2 size-5 animate-spin" />
        Loading
      </div>
    );
  if (error)
    return (
      <Card className="border-rose-500/40 text-danger">
        {error instanceof ApiError ? error.message : "Unable to load control-center data."}
      </Card>
    );
  return <>{children}</>;
}

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "good" | "warn" | "bad";
}) {
  const styles = {
    neutral: "border-border text-muted",
    good: "border-emerald-500/40 bg-emerald-500/10 text-brand",
    warn: "border-yellow-500/40 bg-yellow-500/10 text-warning",
    bad: "border-rose-500/40 bg-rose-500/10 text-danger",
  };
  return (
    <span
      className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-semibold ${styles[tone]}`}
    >
      {children}
    </span>
  );
}
