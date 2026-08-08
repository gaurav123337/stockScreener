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
import { LineChart } from "lucide-react";
import { useState, type FormEvent } from "react";
import type { PortfolioAnalytics } from "@/types/api";

function fmt(value: number, digits = 2): string {
  return new Intl.NumberFormat("en-IN", {
    maximumFractionDigits: digits,
    minimumFractionDigits: 0,
  }).format(value);
}

function parseHoldings(raw: string): Record<string, unknown>[] {
  const lines = raw
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  const holdings: Record<string, unknown>[] = [];
  for (const line of lines) {
    const [symbol, quantity, avgCost] = line.split(/[\s,]+/);
    if (!symbol) continue;
    holdings.push({
      symbol,
      quantity: parseFloat(quantity) || 1,
      avg_cost: parseFloat(avgCost) || 0,
    });
  }
  return holdings;
}

export default function ProPortfolioPage() {
  const { toast } = useToast();
  const { isPro, isPending } = useEntitlements();
  const [raw, setRaw] = useState("");
  const [result, setResult] = useState<PortfolioAnalytics | null>(null);

  const analyticsMutation = useMutation({
    mutationFn: api.portfolioAnalytics,
    onSuccess: setResult,
    onError: (e) => toast(e instanceof Error ? e.message : "Analytics failed"),
  });

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const holdings = parseHoldings(raw);
    if (holdings.length === 0) {
      toast("Enter at least one holding as SYMBOL QUANTITY [AVG_COST] per line");
      return;
    }
    analyticsMutation.mutate(holdings);
  };

  if (isPending) return <LoadingState>Checking your plan…</LoadingState>;

  if (!isPro) {
    return (
      <>
        <Section
          title="Portfolio analytics"
          sub="Sector exposure, valuation mix, dividend-yield estimate and concentration."
        />
        <UpgradePrompt
          feature="Portfolio analytics"
          description="Aggregate risk and valuation analytics across your holdings, powered by the same signal engine as the rest of the product."
        />
      </>
    );
  }

  return (
    <>
      <Section
        title="Portfolio analytics"
        sub="Paste your holdings — one per line as SYMBOL QUANTITY [AVG_COST] — for sector, valuation and concentration analysis."
      />

      <Card className="p-5">
        <form onSubmit={handleSubmit} className="grid gap-3">
          <label className={labelClass}>
            Holdings
            <textarea
              className={controlClass}
              rows={6}
              value={raw}
              onChange={(event) => setRaw(event.target.value)}
              placeholder={"RELIANCE.NS 10 2500\nTCS 5 3500\nHDFCBANK 15 1600"}
              spellCheck={false}
            />
          </label>
          <Button
            className="sm:w-auto"
            disabled={analyticsMutation.isPending}
          >
            <LineChart className="size-4" aria-hidden />
            Analyze portfolio
          </Button>
        </form>
      </Card>

      {analyticsMutation.isPending && <LoadingState>Analyzing portfolio…</LoadingState>}

      {result && !analyticsMutation.isPending && (
        <div className="space-y-3">
          <Card className="p-5">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {[
                { label: "Total value", value: `₹${fmt(result.total_value)}` },
                { label: "Unrealized P&L", value: `₹${fmt(result.total_unrealized_pnl)}` },
                { label: "P&L %", value: `${fmt(result.unrealized_pnl_pct ?? 0, 1)}%` },
                { label: "Est. dividend yield", value: `${fmt(result.weighted_dividend_yield, 2)}%` },
                { label: "Avg signal score", value: fmt(result.avg_signal_score ?? 0, 1) },
                {
                  label: "Concentration (HHI)",
                  value: fmt(result.concentration_herfindahl, 3),
                  hint: "higher = more concentrated",
                },
              ].map(({ label, value, hint }) => (
                <div key={label} className="rounded-panel border border-border bg-surface-raised p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</p>
                  <p className="mt-1 text-xl font-extrabold text-ink">{value}</p>
                  {hint && <p className="text-[11px] text-muted">{hint}</p>}
                </div>
              ))}
            </div>
          </Card>

          <Card className="p-5">
            <h2 className="font-bold text-ink">Sector exposure</h2>
            <div className="mt-3 space-y-2">
              {result.sector_exposure.map(({ sector, value, weight }) => (
                <div key={sector}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-semibold text-ink">{sector}</span>
                    <span className="text-muted">
                      ₹{fmt(value)} · {fmt(weight, 1)}%
                    </span>
                  </div>
                  <div className="mt-1 h-2 overflow-hidden rounded-full bg-surface-raised">
                    <div
                      className="h-full rounded-full bg-brand"
                      style={{ width: `${Math.min(weight, 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card className="p-5">
            <h2 className="font-bold text-ink">Holdings detail</h2>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-max text-left text-sm">
                <thead>
                  <tr className="text-xs uppercase tracking-wide text-muted">
                    <th className="pb-2 pr-3">Symbol</th>
                    <th className="pb-2 pr-3">Sector</th>
                    <th className="pb-2 pr-3 text-right">Weight</th>
                    <th className="pb-2 pr-3 text-right">Score</th>
                    <th className="pb-2 pr-3 text-right">Action</th>
                    <th className="pb-2 text-right">P&L</th>
                  </tr>
                </thead>
                <tbody>
                  {result.holdings.map((holding) => (
                    <tr key={holding.symbol} className="border-t border-border">
                      <td className="py-2 pr-3 font-semibold text-ink">{holding.symbol}</td>
                      <td className="py-2 pr-3 text-muted">{holding.sector}</td>
                      <td className="py-2 pr-3 text-right">{fmt(holding.weight, 1)}%</td>
                      <td className="py-2 pr-3 text-right">
                        {holding.score != null ? fmt(holding.score, 1) : "—"}
                      </td>
                      <td className="py-2 pr-3 text-right">
                        <span className="text-muted">{holding.action ?? "—"}</span>
                      </td>
                      <td
                        className={`py-2 text-right font-semibold ${
                          holding.unrealized_pnl >= 0 ? "text-emerald-600" : "text-rose-600"
                        }`}
                      >
                        {holding.unrealized_pnl >= 0 ? "+" : ""}₹{fmt(holding.unrealized_pnl)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
    </>
  );
}
