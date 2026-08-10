import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/endpoints";
import { Section } from "@/components/Section";
import { Card } from "@/components/ui/Card";
import { LoadingState } from "@/components/ui/Spinner";
import { useAuth } from "@/features/auth/auth-context";
import { GitCommitHorizontal, Lightbulb, LineChart } from "lucide-react";

function fmt(value: number | null | undefined, digits = 1) {
  if (value == null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export default function FeedbackLoopPage() {
  const { user } = useAuth();
  const isOwner = user?.role === "product_owner";

  const outcomesQuery = useQuery({
    queryKey: ["feedback-loop", "outcomes"],
    queryFn: api.feedbackOutcomes,
    staleTime: 60 * 60 * 1000,
  });
  const suggestionsQuery = useQuery({
    queryKey: ["feedback-loop", "suggestions"],
    queryFn: api.feedbackSuggestions,
    staleTime: 60 * 60 * 1000,
  });
  const changelogQuery = useQuery({
    queryKey: ["feedback-loop", "changelog"],
    queryFn: api.feedbackChangelog,
    staleTime: 60 * 60 * 1000,
  });

  const outcomes = outcomesQuery.data;
  const suggestions = suggestionsQuery.data;
  const entries = changelogQuery.data?.entries ?? [];

  return (
    <>
      <Section
        title="Model feedback loop"
        sub="Every signal is logged and scored against what actually happened. When the score stops predicting outcomes, we suggest a weight change — and publish every change so you can see exactly what moved."
      />

      {outcomesQuery.isPending ? (
        <LoadingState />
      ) : outcomes ? (
        <Card className="p-5">
          <h2 className="flex items-center gap-2 font-bold text-ink">
            <LineChart className="size-5 text-brand" aria-hidden />
            Realized outcomes
          </h2>
          <p className="mt-1 text-xs text-muted">
            {outcomes.evaluated} matured signals · overall hit rate{" "}
            <span className="font-bold text-ink">{fmt(outcomes.overall_hit_rate)}</span>
            {outcomes.score_predictiveness != null && (
              <span>
                {" "}
                · score predictiveness{" "}
                <span
                  className={
                    outcomes.score_predictiveness > 0 ? "font-bold text-emerald-600" : "font-bold text-amber-600"
                  }
                >
                  {fmt(outcomes.score_predictiveness)}
                </span>
              </span>
            )}
          </p>

          <div className="mt-4 grid gap-2 sm:grid-cols-3">
            {(["high", "mid", "low"] as const).map((band) => {
              const stats = outcomes.by_score_band[band];
              return (
                <div key={band} className="rounded-panel border border-border bg-surface-raised p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted">
                    {band}-score signals
                  </p>
                  <p className="mt-1 text-2xl font-bold text-ink">
                    {stats ? fmt(stats.hit_rate) : "—"}
                  </p>
                  <p className="text-xs text-muted">{stats ? `${stats.n} signals` : "no data"}</p>
                </div>
              );
            })}
          </div>
        </Card>
      ) : null}

      {suggestionsQuery.isPending ? (
        <LoadingState />
      ) : suggestions ? (
        <Card className="mt-3 p-5">
          <h2 className="flex items-center gap-2 font-bold text-ink">
            <Lightbulb className="size-5 text-brand" aria-hidden />
            Suggested weight changes
          </h2>
          <p className="mt-1 text-sm leading-6 text-ink">{suggestions.message}</p>
          {suggestions.suggestions.length > 0 ? (
            <div className="mt-3 grid gap-2">
              {suggestions.suggestions.map((s) => (
                <div key={s.pillar} className="rounded-panel border border-amber-500/40 bg-amber-500/5 p-3">
                  <p className="flex flex-wrap items-center justify-between gap-2 text-sm font-bold text-ink">
                    {s.pillar}
                    <span className="text-xs font-semibold text-muted">
                      {s.current_weight} → {s.suggested_weight} pts ({s.direction})
                    </span>
                  </p>
                  <p className="mt-1 text-xs leading-5 text-muted">{s.reason}</p>
                </div>
              ))}
              <p className="text-xs leading-5 text-muted">
                Suggestions are never applied automatically — a product owner reviews and publishes
                them through the changelog below.
              </p>
            </div>
          ) : (
            <p className="mt-2 text-xs text-muted">No weight changes suggested right now.</p>
          )}
        </Card>
      ) : null}

      <Card className="mt-3 p-5">
        <h2 className="flex items-center gap-2 font-bold text-ink">
          <GitCommitHorizontal className="size-5 text-brand" aria-hidden />
          Published changes
        </h2>
        {changelogQuery.isPending ? (
          <LoadingState />
        ) : entries.length === 0 ? (
          <p className="mt-2 text-sm text-muted">
            No changes published yet. {isOwner ? "Publish from the control center when ready." : "Check back later."}
          </p>
        ) : (
          <div className="mt-2 space-y-3">
            {entries.map((entry) => (
              <div key={entry.entry_id} className="rounded-panel border border-border bg-surface-raised p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-bold text-ink">{entry.title}</p>
                  <span className="text-xs text-muted">
                    v{entry.version} · {entry.date}
                  </span>
                </div>
                {entry.summary && <p className="mt-1 text-xs leading-5 text-muted">{entry.summary}</p>}
                {Object.keys(entry.weight_changes).length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {Object.entries(entry.weight_changes).map(([key, change]) => (
                      <span
                        key={key}
                        className="rounded-full border border-border bg-surface px-2 py-0.5 text-[11px] font-semibold text-muted"
                      >
                        {key}: {String(change.old)} → {String(change.new)}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
    </>
  );
}
