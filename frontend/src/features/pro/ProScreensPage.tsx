import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/api/endpoints";
import { useEntitlements } from "./hooks/useEntitlements";
import { UpgradePrompt } from "./components/UpgradePrompt";
import { Section } from "@/components/Section";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { controlClass, labelClass } from "@/components/ui/styles";
import { LoadingState } from "@/components/ui/Spinner";
import { useToast } from "@/app/useToast";
import { queryClient } from "@/app/queryClient";
import { BellRing, Play, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import type { AlertEvaluation } from "@/types/api";

export default function ProScreensPage() {
  const { toast } = useToast();
  const { isPro, entitlements } = useEntitlements();
  const [name, setName] = useState("");
  const [filterExpr, setFilterExpr] = useState("");
  const [alertEmail, setAlertEmail] = useState("");
  const [alertEnabled, setAlertEnabled] = useState(false);
  const [lastResult, setLastResult] = useState<AlertEvaluation | null>(null);

  const screensQuery = useQuery({
    queryKey: ["pro", "screens"],
    queryFn: api.listSavedScreens,
  });

  const saveMutation = useMutation({
    mutationFn: api.saveScreen,
    onSuccess: async () => {
      setName("");
      setFilterExpr("");
      setAlertEmail("");
      setAlertEnabled(false);
      toast("Screen saved");
      await queryClient.invalidateQueries({ queryKey: ["pro", "screens"] });
    },
    onError: (e) => toast(e instanceof Error ? e.message : "Could not save screen"),
  });

  const deleteMutation = useMutation({
    mutationFn: api.deleteScreen,
    onSuccess: async () => {
      toast("Screen deleted");
      await queryClient.invalidateQueries({ queryKey: ["pro", "screens"] });
    },
    onError: (e) => toast(e instanceof Error ? e.message : "Could not delete screen"),
  });

  const evaluateMutation = useMutation({
    mutationFn: api.evaluateScreen,
    onSuccess: (result) => setLastResult(result),
    onError: (e) => toast(e instanceof Error ? e.message : "Could not evaluate screen"),
  });

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    saveMutation.mutate({
      name,
      filter_expr: filterExpr.trim(),
      alert_enabled: isPro && alertEnabled,
      alert_email: isPro && alertEnabled ? alertEmail.trim() || null : null,
    });
  };

  const screens = screensQuery.data?.screens ?? [];

  return (
    <>
      <Section
        title="Saved screens"
        sub="Persist any custom filter and re-run it against the live universe. Email alerts are a Pro feature."
      />

      {!isPro && entitlements && (
        <p className="mb-3 text-sm text-muted">
          Free tier includes {entitlements.limits.saved_screens ?? 1} saved screen.
        </p>
      )}

      <Card className="p-5">
        <form onSubmit={handleSubmit} className="grid gap-3">
          <label className={labelClass}>
            Name
            <input
              className={controlClass}
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="e.g. Undervalued large-caps"
              required
            />
          </label>
          <label className={labelClass}>
            Filter expression
            <input
              className={controlClass}
              value={filterExpr}
              onChange={(event) => setFilterExpr(event.target.value)}
              placeholder="e.g. pe > 10 and peg < 1 and roe > 15"
            />
          </label>
          {isPro && (
            <label className={labelClass}>
              Email for alerts (optional)
              <input
                className={controlClass}
                type="email"
                value={alertEmail}
                onChange={(event) => setAlertEmail(event.target.value)}
                placeholder="you@example.com"
              />
            </label>
          )}
          <div className="flex flex-wrap items-center gap-3">
            {isPro && (
              <label className="flex items-center gap-2 text-sm font-semibold text-ink">
                <input
                  type="checkbox"
                  className="size-4 accent-emerald-600"
                  checked={alertEnabled}
                  onChange={(event) => setAlertEnabled(event.target.checked)}
                />
                Enable email alerts
              </label>
            )}
            <Button
              className="sm:w-auto"
              disabled={saveMutation.isPending || !name.trim()}
            >
              <Plus className="size-4" aria-hidden />
              Save screen
            </Button>
          </div>
          {!isPro && (
            <p className="text-xs leading-5 text-muted">
              Alerts unlock with Pro. You can still save {entitlements?.limits.saved_screens ?? 1}{" "}
              screen on Free.
            </p>
          )}
        </form>
      </Card>

      {screensQuery.isPending ? (
        <LoadingState />
      ) : screens.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted">No saved screens yet.</p>
      ) : (
        <div className="space-y-3">
          {screens.map((screen) => (
            <Card key={screen.screen_id} className="p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="font-bold text-ink">{screen.name}</h3>
                  <p className="mt-0.5 break-all font-mono text-xs text-muted">
                    {screen.filter_expr || "(unfiltered)"}
                  </p>
                  {screen.alert_enabled && (
                    <p className="mt-1 inline-flex items-center gap-1 text-xs font-semibold text-brand">
                      <BellRing className="size-3.5" aria-hidden />
                      Alerts on · {screen.last_match_count} matched
                    </p>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    className="sm:w-auto"
                    disabled={!isPro || evaluateMutation.isPending}
                    onClick={() => evaluateMutation.mutate(screen.screen_id)}
                    title={isPro ? "Run now" : "Pro feature"}
                  >
                    <Play className="size-4" aria-hidden />
                    Run
                  </Button>
                  <Button
                    variant="danger"
                    className="sm:w-auto"
                    disabled={deleteMutation.isPending}
                    onClick={() => deleteMutation.mutate(screen.screen_id)}
                    aria-label={`Delete ${screen.name}`}
                  >
                    <Trash2 className="size-4" aria-hidden />
                    <span className="hidden sm:inline">Delete</span>
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {!isPro && (
        <div className="mt-4">
          <UpgradePrompt
            feature="Email alerts on your saved screens"
            description="Get notified when a new stock matches a screen you care about."
          />
        </div>
      )}

      {lastResult && (
        <Card className="mt-4 border-brand/40 p-5">
          <h3 className="font-bold text-ink">
            {lastResult.screen.name} — {lastResult.matched.length} matches
          </h3>
          {lastResult.email_sent && (
            <p className="mt-1 text-sm font-semibold text-emerald-600">
              Alert dispatched to {lastResult.screen.alert_email}
            </p>
          )}
          <p className="mt-1 text-xs text-muted">
            New matches since last run: {lastResult.new_matches}
          </p>
          {lastResult.matched.length > 0 && (
            <ul className="mt-3 grid gap-1 sm:grid-cols-2">
              {lastResult.matched.map((row) => (
                <li
                  key={String(row.symbol)}
                  className="flex items-center justify-between gap-2 rounded-lg border border-border bg-surface-raised px-3 py-2 text-sm"
                >
                  <span className="truncate font-semibold text-ink">{String(row.symbol)}</span>
                  <span className="shrink-0 text-xs text-muted">
                    {row.score != null ? `score ${Number(row.score).toFixed(1)}` : "—"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </>
  );
}
