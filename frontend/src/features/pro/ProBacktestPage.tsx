import { useMutation } from "@tanstack/react-query";
import { api } from "@/api/endpoints";
import { useEntitlements } from "./hooks/useEntitlements";
import { UpgradePrompt } from "./components/UpgradePrompt";
import { Section } from "@/components/Section";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { controlClass, labelClass } from "@/components/ui/styles";
import { LoadingState } from "@/components/ui/Spinner";
import { useToast } from "@/app/useToast";
import { FlaskConical } from "lucide-react";
import { useState, type FormEvent } from "react";
import type { StrategyBacktest } from "@/types/api";

function pct(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function upDown(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

export default function ProBacktestPage() {
  const { toast } = useToast();
  const { isPro, isPending } = useEntitlements();
  const [strategy, setStrategy] = useState("balanced");
  const [symbols, setSymbols] = useState("");
  const [result, setResult] = useState<StrategyBacktest | null>(null);

  const backtestMutation = useMutation({
    mutationFn: api.strategyBacktest,
    onSuccess: setResult,
    onError: (e) => toast(e instanceof Error ? e.message : "Backtest failed"),
  });

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const symbolList = symbols
      .split(/[\s,]+/)
      .map((symbol) => symbol.trim())
      .filter(Boolean);
    backtestMutation.mutate({
      strategy: strategy.trim() || "default",
      symbols: symbolList.length ? symbolList : undefined,
    });
  };

  if (isPending) return <LoadingState>Checking your plan…</LoadingState>;

  if (!isPro) {
    return (
      <>
        <Section
          title="Strategy backtests"
          sub="Focused, per-strategy walk-forward replays on the symbols you care about."
        />
        <UpgradePrompt
          feature="Per-strategy deep backtests"
          description="Replay the signal engine over the names you watch and see dated hit-rates vs the benchmark — no lookahead, no fees, honest evidence."
        />
      </>
    );
  }

  return (
    <>
      <Section
        title="Strategy backtests"
        sub="Walk-forward replay of the signal engine on your chosen symbols. Leave symbols empty to use a default slice of the universe."
      />

      <Card className="p-5">
        <form onSubmit={handleSubmit} className="grid gap-3">
          <label className={labelClass}>
            Strategy name
            <input
              className={controlClass}
              value={strategy}
              onChange={(event) => setStrategy(event.target.value)}
              placeholder="e.g. momentum-q3"
            />
          </label>
          <label className={labelClass}>
            Symbols (space- or comma-separated)
            <input
              className={controlClass}
              value={symbols}
              onChange={(event) => setSymbols(event.target.value)}
              placeholder="RELIANCE.NS TCS HDFCBANK"
              spellCheck={false}
            />
          </label>
          <Button className="sm:w-auto" disabled={backtestMutation.isPending}>
            <FlaskConical className="size-4" aria-hidden />
            Run backtest
          </Button>
        </form>
      </Card>

      {backtestMutation.isPending && <LoadingState>Replaying signals…</LoadingState>}

      {result && !backtestMutation.isPending && (
        <div className="space-y-3">
          <Card className="p-5">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="font-bold text-ink">
                {result.strategy} — {result.universe_size} symbols · {result.signals} signals
              </h2>
              <span className="text-xs text-muted">
                {result.window_start} → {result.window_end}
              </span>
            </div>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-max text-left text-sm">
                <thead>
                  <tr className="text-xs uppercase tracking-wide text-muted">
                    <th className="pb-2 pr-3">Horizon</th>
                    <th className="pb-2 pr-3 text-right">Signals</th>
                    <th className="pb-2 pr-3 text-right">Hit rate</th>
                    <th className="pb-2 pr-3 text-right">Avg return</th>
                    <th className="pb-2 pr-3 text-right">Benchmark</th>
                    <th className="pb-2 pr-3 text-right">vs Benchmark</th>
                    <th className="pb-2 text-right">Max DD</th>
                  </tr>
                </thead>
                <tbody>
                  {result.horizons.map((h) => (
                    <tr key={h.horizon_days} className="border-t border-border">
                      <td className="py-2 pr-3 font-semibold text-ink">{h.horizon_days}d</td>
                      <td className="py-2 pr-3 text-right">{h.n}</td>
                      <td className="py-2 pr-3 text-right">{pct(h.hit_rate)}</td>
                      <td className="py-2 pr-3 text-right">{upDown(h.avg_return)}</td>
                      <td className="py-2 pr-3 text-right">{upDown(h.benchmark_avg_return)}</td>
                      <td
                        className={`py-2 pr-3 text-right font-semibold ${
                          (h.vs_benchmark ?? 0) >= 0 ? "text-emerald-600" : "text-rose-600"
                        }`}
                      >
                        {upDown(h.vs_benchmark)}
                      </td>
                      <td className="py-2 text-right text-muted">{pct(h.max_drawdown)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {result.methodology?.length > 0 && (
            <Card className="p-4">
              <h3 className="font-bold text-ink">Methodology</h3>
              <ul className="mt-2 list-inside list-disc space-y-1 text-xs leading-5 text-muted">
                {result.methodology.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      )}
    </>
  );
}
