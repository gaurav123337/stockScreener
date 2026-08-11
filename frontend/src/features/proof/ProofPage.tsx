import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/endpoints";
import { Section } from "@/components/Section";
import { Card } from "@/components/ui/Card";
import { LoadingState } from "@/components/ui/Spinner";
import { BarChart3, BookOpenCheck, ShieldCheck, TrendingUp } from "lucide-react";

function fmt(value: number | null | undefined, suffix = "") {
  if (value == null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(1)}${suffix}`;
}

export default function ProofPage() {
  const scorecardQuery = useQuery({
    queryKey: ["scorecard"],
    queryFn: api.monthlyScorecard,
    staleTime: 60 * 60 * 1000,
  });
  const storiesQuery = useQuery({ queryKey: ["stories"], queryFn: api.successStories });

  const scorecard = scorecardQuery.data;

  return (
    <>
      <Section
        title="Track record"
        sub="Dated evidence instead of vague promises: the published walk-forward backtest and the live verification log, plus educational walkthroughs of how real users approach the tool."
      />

      {scorecardQuery.isPending ? (
        <LoadingState />
      ) : scorecard ? (
        <Card className="p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="flex items-center gap-2 font-bold text-ink">
              <BarChart3 className="size-5 text-brand" aria-hidden />
              Monthly scorecard · {scorecard.period}
            </h2>
            <span className="text-xs text-muted">
              generated {new Date(scorecard.generated_at).toLocaleDateString("en-IN")}
            </span>
          </div>
          <p className="mt-1 text-xs leading-5 text-muted">
            {scorecard.universe_size} symbols · {scorecard.window_start?.slice(0, 10)} →{" "}
            {scorecard.window_end?.slice(0, 10)} · vs {scorecard.benchmark_symbol}
          </p>

          <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {scorecard.horizons.map((h) => (
              <div
                key={h.horizon_days}
                className="rounded-panel border border-border bg-surface-raised p-3"
              >
                <p className="text-xs font-semibold uppercase tracking-wide text-muted">
                  {h.horizon_days}d horizon
                </p>
                <p className="mt-1 text-2xl font-bold text-ink">{fmt(h.hit_rate)}%</p>
                <p className="text-xs text-muted">
                  hit rate · {h.n} signals · vs benchmark {fmt(h.vs_benchmark, "pp")}
                </p>
                <p className="mt-1 text-xs text-muted">max drawdown {fmt(h.max_drawdown)}%</p>
              </div>
            ))}
            {scorecard.live_evaluated != null && (
              <div className="rounded-panel border border-brand/40 bg-brand/5 p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-brand">
                  Live verification
                </p>
                <p className="mt-1 text-2xl font-bold text-ink">
                  {fmt(scorecard.live_overall_hit_rate)}%
                </p>
                <p className="text-xs text-muted">
                  {scorecard.live_evaluated} matured signals from the live log
                </p>
              </div>
            )}
          </div>

          <p className="mt-3 text-xs leading-5 text-muted">
            <ShieldCheck className="mr-1 inline size-3.5 text-brand" aria-hidden />
            {scorecard.source}
          </p>
          <p className="mt-2 text-[11px] leading-4 text-muted">{scorecard.disclaimer}</p>
        </Card>
      ) : null}

      <div className="mt-6">
        <h2 className="mb-2 flex items-center gap-2 font-bold text-ink">
          <BookOpenCheck className="size-5 text-brand" aria-hidden />
          How people use it
        </h2>
        {storiesQuery.isPending ? (
          <LoadingState />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {(storiesQuery.data?.stories ?? []).map((story) => (
              <Card key={story.id} className="flex flex-col p-5">
                <span className="inline-flex w-fit items-center gap-1 rounded-full bg-brand/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-brand">
                  <TrendingUp className="size-3" aria-hidden />
                  Illustrative walkthrough
                </span>
                <h3 className="mt-2 font-bold leading-snug text-ink">{story.title}</h3>
                <p className="mt-1 text-xs font-semibold text-muted">{story.persona}</p>
                <p className="mt-2 flex-1 text-sm leading-6 text-ink">{story.walkthrough}</p>
                <p className="mt-3 rounded-panel bg-surface-raised p-2.5 text-xs leading-5 text-muted">
                  {story.lesson}
                </p>
              </Card>
            ))}
          </div>
        )}
        <p className="mt-2 text-[11px] text-muted">
          These are illustrative educational examples, not claims about real user returns.
        </p>
      </div>
    </>
  );
}
