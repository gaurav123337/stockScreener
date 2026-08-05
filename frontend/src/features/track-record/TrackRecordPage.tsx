import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, BarChart3, CalendarClock, Database, RefreshCw, ShieldQuestion } from "lucide-react";
import { api } from "@/api/endpoints";
import { useAuth } from "@/features/auth/auth-context";
import { useToast } from "@/app/useToast";
import { Button } from "@/components/ui/Button";
import { Disclaimer } from "@/components/Disclaimer";
import { Section } from "@/components/Section";
import { Card, CardTitle } from "@/components/ui/Card";
import { LoadingState } from "@/components/ui/Spinner";
import type { HorizonStats } from "@/types/api";

/** Percentage like 0.0156 -> "+1.6%". Null-safe. */
function signedPct(n: number | null | undefined): string {
  if (n === null || n === undefined) return "-";
  return `${n > 0 ? "+" : ""}${(n * 100).toFixed(1)}%`;
}

/** 0.445 -> "44.5%", null -> "-". */
function rate(n: number | null | undefined): string {
  return n === null || n === undefined ? "-" : `${n.toFixed(1)}%`;
}

function StatBox({ label, value, tone = "text-ink" }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface-raised p-3">
      <div className="text-[11px] text-muted">{label}</div>
      <div className={`mt-0.5 text-lg font-bold ${tone}`}>{value}</div>
    </div>
  );
}

function HorizonTable({ horizons }: { horizons: HorizonStats[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-border text-[11px] uppercase text-muted">
            <th className="py-2 pr-3 font-semibold">Horizon</th>
            <th className="py-2 pr-3 font-semibold">Signals</th>
            <th className="py-2 pr-3 font-semibold">Hit-rate</th>
            <th className="py-2 pr-3 font-semibold">Avg return</th>
            <th className="py-2 pr-3 font-semibold">Avg win / loss</th>
            <th className="py-2 pr-3 font-semibold">Max drawdown</th>
            <th className="py-2 pr-3 font-semibold">Benchmark</th>
            <th className="py-2 font-semibold">vs Benchmark</th>
          </tr>
        </thead>
        <tbody>
          {horizons.map((h) => (
            <tr key={h.horizon_days} className="border-b border-border/60">
              <td className="py-2 pr-3 font-semibold text-ink">{h.horizon_days}d</td>
              <td className="py-2 pr-3 text-muted">{h.n}</td>
              <td className="py-2 pr-3 font-bold text-ink">{rate(h.hit_rate)}</td>
              <td className="py-2 pr-3 text-muted">{signedPct(h.avg_return)}</td>
              <td className="py-2 pr-3 text-muted">
                {signedPct(h.avg_win)}
                <span className="text-muted/60"> / </span>
                {signedPct(h.avg_loss)}
              </td>
              <td className="py-2 pr-3 text-muted">{signedPct(h.max_drawdown)}</td>
              <td className="py-2 pr-3 text-muted">{signedPct(h.benchmark_avg_return)}</td>
              <td
                className={`py-2 font-bold ${
                  h.vs_benchmark !== null && h.vs_benchmark > 0 ? "text-brand" : "text-muted"
                }`}
              >
                {signedPct(h.vs_benchmark)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function TrackRecordPage() {
  const { user } = useAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const backtestQuery = useQuery({
    queryKey: ["backtest"],
    queryFn: api.backtest,
    staleTime: 60_000,
  });
  const verifyQuery = useQuery({
    queryKey: ["verify"],
    queryFn: api.verify,
    staleTime: 60_000,
  });
  const complianceQuery = useQuery({ queryKey: ["compliance"], queryFn: api.compliance });

  const refreshMutation = useMutation({
    mutationFn: api.backtestRun,
    onSuccess: () => {
      toast("Track record regenerated");
      void queryClient.invalidateQueries({ queryKey: ["backtest"] });
      void queryClient.invalidateQueries({ queryKey: ["verify"] });
    },
    onError: (e) => toast(e instanceof Error ? e.message : "Regenerate failed"),
  });

  const isOwner = user?.role === "product_owner";

  if (backtestQuery.isLoading || verifyQuery.isLoading) {
    return <LoadingState>Loading track record…</LoadingState>;
  }

  const report = backtestQuery.data;
  const live = verifyQuery.data;

  const primary = report?.horizons[0];
  const buy = primary?.by_action["BUY"];
  const sell = primary?.by_action["SELL"];

  return (
    <>
      <Section
        title="Track Record"
        sub="How the Signal Score has actually performed over time. Every number is dated, walk-forward evidence from the live engine — not a backfilled claim."
      />

      {backtestQuery.isError && (
        <Card className="border-rose-500/40">
          <CardTitle>Track record unavailable</CardTitle>
          <p className="mt-2 text-sm text-muted">
            The walk-forward replay could not be generated right now. Check that market data is
            reachable and try again later.
          </p>
        </Card>
      )}

      {report && (
        <>
          <Card>
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <div className="flex items-start gap-2">
                  <BarChart3 className="mt-0.5 size-4 shrink-0 text-brand" aria-hidden />
                  <CardTitle>Published walk-forward record</CardTitle>
                </div>
                <div className="mt-1 text-xs text-muted">
                  {report.universe_size} NIFTY50 stocks replayed from{" "}
                  {report.window_start?.slice(0, 10)} to {report.window_end?.slice(0, 10)}. Generated{" "}
                  {report.generated_at ? new Date(report.generated_at).toLocaleString() : "-"}.
                </div>
              </div>
              {isOwner && (
                <Button
                  variant="secondary"
                  fullWidth={false}
                  onClick={() => refreshMutation.mutate()}
                  disabled={refreshMutation.isPending}
                >
                  <RefreshCw className="size-4" aria-hidden />
                  {refreshMutation.isPending ? "Regenerating…" : "Refresh"}
                </Button>
              )}
            </div>

            <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
              <StatBox label="30d hit-rate (all signals)" value={rate(primary?.hit_rate)} />
              <StatBox
                label="BUY hit-rate (actionable)"
                value={rate(buy?.hit_rate)}
                tone="text-brand"
              />
              <StatBox label="SELL hit-rate" value={rate(sell?.hit_rate)} />
              <StatBox
                label="30d BUY avg return"
                value={signedPct(buy?.avg_return)}
                tone={buy && buy.avg_return > 0 ? "text-brand" : "text-ink"}
              />
            </div>

            <div className="mt-3">
              <HorizonTable horizons={report.horizons} />
            </div>
          </Card>

          {live && (
            <Card>
              <div className="flex items-start gap-2">
                <Activity className="mt-0.5 size-4 shrink-0 text-brand" aria-hidden />
                <CardTitle>Live rolling verification</CardTitle>
              </div>
              <p className="mt-1 text-xs text-muted">
                Every signal is measured at each horizon as soon as it elapses — live calls served
                to users, plus the walk-forward replay backfilled into the log (stamped{" "}
                <code className="rounded bg-surface-raised px-1">system/backtest</code> for
                auditability). {live.total_evaluated} of {live.evaluated_now} logged signals have
                matured.
              </p>
              {live.overall_hit_rate !== null ? (
                <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
                  <StatBox label="Overall hit-rate" value={rate(live.overall_hit_rate)} />
                  <StatBox label="30d signals" value={String(live.horizons?.[0]?.n ?? 0)} />
                  <StatBox label="90d signals" value={String(live.horizons?.[1]?.n ?? 0)} />
                  <StatBox label="365d signals" value={String(live.horizons?.[2]?.n ?? 0)} />
                </div>
              ) : (
                <p className="mt-3 text-sm text-muted">
                  No signals have matured yet — the first results appear 30 days after the first
                  call is logged.
                </p>
              )}
            </Card>
          )}

          <Card>
            <div className="flex items-start gap-2">
              <Database className="mt-0.5 size-4 shrink-0 text-muted" aria-hidden />
              <CardTitle>Methodology</CardTitle>
            </div>
            <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm leading-6 text-muted">
              {report.methodology.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
          </Card>

          <Card>
            <div className="flex items-start gap-2">
              <ShieldQuestion className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden />
              <CardTitle>Honest caveats</CardTitle>
            </div>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-muted">
              {report.notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
            <div className="mt-3 flex items-start gap-2 text-xs text-muted">
              <CalendarClock className="mt-0.5 size-4 shrink-0" aria-hidden />
              <span>
                Confidence shown on each recommendation measures pillar agreement and signal
                strength — it is a transparency measure, not a probability of profit.
              </span>
            </div>
          </Card>
        </>
      )}

      <Disclaimer compliance={complianceQuery.data} />
    </>
  );
}
