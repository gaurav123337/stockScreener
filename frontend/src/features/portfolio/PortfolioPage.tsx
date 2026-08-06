import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Layers, Plus, ShieldAlert, TrendingUp, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/api/endpoints";
import { useToast } from "@/app/useToast";
import { AssetSplitBar } from "@/components/AssetSplitBar";
import { Disclaimer } from "@/components/Disclaimer";
import { Section } from "@/components/Section";
import { Card, CardTitle } from "@/components/ui/Card";
import { LoadingState } from "@/components/ui/Spinner";
import { cn } from "@/lib/cn";
import { pct, stripExchangeSuffix } from "@/lib/format";
import type { ScanRow } from "@/types/api";
import { StockAutocomplete } from "@/features/scan/components/StockAutocomplete";
import { useStockAutocomplete } from "@/features/scan/hooks/useStockAutocomplete";

const badgeTone: Record<string, string> = {
  Low: "bg-emerald-500/15 text-brand",
  Medium: "bg-amber-400/15 text-warning",
  High: "bg-rose-500/15 text-danger",
};

const actionBadge: Record<string, string> = {
  BUY: "bg-emerald-500/15 text-brand",
  SELL: "bg-rose-500/15 text-danger",
  HOLD: "bg-yellow-400/15 text-warning",
};

export default function PortfolioPage() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const complianceQuery = useQuery({ queryKey: ["compliance"], queryFn: api.compliance });
  const profileQuery = useQuery({ queryKey: ["risk-profile"], queryFn: api.getRiskProfile });
  const watchlistQuery = useQuery({ queryKey: ["watchlist"], queryFn: api.watchlist });
  const autocomplete = useStockAutocomplete();
  const [localSymbols, setLocalSymbols] = useState<string[] | null>(null);

  const symbols = localSymbols ?? watchlistQuery.data?.symbols ?? [];

  const holdingsQuery = useQuery({
    queryKey: ["holdings", symbols],
    queryFn: async () => {
      const rows = await Promise.all(
        symbols.map((symbol) =>
          api.recommend(symbol).catch(
            (e: unknown): ScanRow => ({
              symbol,
              name: null,
              sector: null,
              action: "HOLD",
              score: 0,
              price: null,
              entry: null,
              target: null,
              stop_loss: null,
              rr: null,
              rsi: null,
              sma50: null,
              sma200: null,
              pe: null,
              peg: null,
              roe: null,
              reasons: null,
              error: e instanceof Error ? e.message : "Request failed",
            }),
          ),
        ),
      );
      return rows;
    },
    enabled: symbols.length > 0,
    staleTime: 60_000,
  });

  const saveWatchlist = useMutation({
    mutationFn: (next: string[]) => api.setWatchlist(next),
    onSuccess: (res) => {
      setLocalSymbols(res.symbols);
      void queryClient.invalidateQueries({ queryKey: ["watchlist"] });
    },
  });

  const addSymbol = (symbol: string) => {
    const normalized = symbol.toUpperCase();
    if (symbols.map((s) => s.toUpperCase()).includes(normalized)) {
      toast("Already in your watchlist");
    } else {
      saveWatchlist.mutate([...symbols, normalized]);
    }
    autocomplete.setSearch("");
    autocomplete.setIsOpen(false);
  };

  const removeSymbol = (symbol: string) => {
    saveWatchlist.mutate(symbols.filter((s) => s !== symbol));
  };

  const profile = profileQuery.data;
  const profileLevel = profile?.level ?? "moderate";
  const rows = holdingsQuery.data ?? [];
  const valid = rows.filter((r) => !r.error);

  const riskCounts: Record<string, number> = { Low: 0, Medium: 0, High: 0 };
  const sectors = new Map<string, number>();
  let scoreSum = 0;
  for (const row of valid) {
    const badge = row.risk_badge ?? "Low";
    if (badge in riskCounts) riskCounts[badge] += 1;
    if (row.sector) sectors.set(row.sector, (sectors.get(row.sector) ?? 0) + 1);
    scoreSum += row.score;
  }
  const sectorSpread = [...sectors.entries()].sort((a, b) => b[1] - a[1]);
  const avgScore = valid.length ? Math.round(scoreSum / valid.length) : null;
  const dominantRisk = valid.length
    ? (Object.keys(riskCounts) as Array<keyof typeof riskCounts>).reduce(
        (best, key) => (riskCounts[key] > riskCounts[best] ? key : best),
        "Low" as keyof typeof riskCounts,
      )
    : null;

  return (
    <>
      <Section
        title="My portfolio"
        sub="A plain-language look at your watchlist: what you're holding, how risky it is, and how spread out your sectors are."
      />

      <Card>
        <div className="flex items-start gap-2">
          <Plus className="mt-0.5 size-4 shrink-0 text-brand" aria-hidden />
          <CardTitle>Add a stock to your portfolio</CardTitle>
        </div>
        <div className="mt-2">
          <StockAutocomplete
            value={autocomplete.search}
            results={autocomplete.results}
            isOpen={autocomplete.isOpen}
            containerRef={autocomplete.containerRef}
            onChange={autocomplete.setSearch}
            onSelect={addSymbol}
            onClose={() => autocomplete.setIsOpen(false)}
          />
        </div>
      </Card>

      <Card>
        <div className="flex items-start gap-2">
          <Layers className="mt-0.5 size-4 shrink-0 text-brand" aria-hidden />
          <CardTitle>At a glance</CardTitle>
        </div>

        {valid.length === 0 ? (
          <p className="mt-2 text-sm text-muted">
            Nothing here yet — add a few stocks above to see the summary.
          </p>
        ) : (
          <>
            <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
              <Stat label="Stocks tracked" value={String(valid.length)} />
              <Stat
                label="Overall feel"
                value={`${dominantRisk ?? "-"} risk`}
              />
              <Stat label="Average signal score" value={avgScore !== null ? String(avgScore) : "-"} />
              <Stat
                label="Sectors covered"
                value={String(sectorSpread.length)}
              />
            </div>

            <div className="mt-3">
              <div className="mb-1.5 text-xs font-bold uppercase text-muted">Sector spread</div>
              <div className="flex flex-wrap gap-1.5">
                {sectorSpread.length === 0 && (
                  <span className="text-xs text-muted">No sector data yet.</span>
                )}
                {sectorSpread.map(([sector, count]) => (
                  <span
                    key={sector}
                    className="rounded-full border border-border bg-surface-raised px-2.5 py-1 text-[11px] font-semibold text-muted"
                  >
                    {sector} × {count}
                  </span>
                ))}
              </div>
            </div>

            {profile?.asset_split && (
              <div className="mt-4">
                <div className="mb-1.5 text-xs font-bold uppercase text-muted">
                  Your target mix ({profile?.label ?? profileLevel})
                </div>
                <AssetSplitBar split={profile.asset_split} />
              </div>
            )}

            {profile?.expected_return_range && (
              <div className="mt-4 rounded-lg border border-border bg-surface-raised p-3 text-xs leading-5 text-muted">
                <div className="flex items-start gap-2">
                  <TrendingUp className="mt-0.5 size-3.5 shrink-0 text-brand" aria-hidden />
                  <span>
                    Expected yearly return range for your {(profile?.label ?? profileLevel).toLowerCase()} mix:{" "}
                    <strong className="text-ink">
                      {pct(profile.expected_return_range[0])}–{pct(profile.expected_return_range[1])}
                    </strong>
                    . A conservative outcome might land around{" "}
                    {pct(Math.max(0.04, profile.expected_return_range[0] - 0.02))}–{pct(Math.max(0.06, profile.expected_return_range[1] - 0.04))}.
                    These are assumptions to plan with, not promises.
                  </span>
                </div>
              </div>
            )}
          </>
        )}
      </Card>

      {holdingsQuery.isFetching && <LoadingState>Refreshing prices…</LoadingState>}

      {valid.length > 0 && (
        <Card>
          <CardTitle>Your holdings</CardTitle>
          <div className="mt-2 grid gap-2">
            {rows.map((row) => (
              <div
                key={row.symbol}
                className="rounded-lg border border-border bg-surface-raised p-3"
              >
                <div className="flex items-baseline justify-between gap-2">
                  <div>
                    <span className="text-[15px] font-bold text-ink">
                      {stripExchangeSuffix(row.symbol)}
                    </span>
                    {row.name && <span className="ml-1.5 text-xs text-muted">{row.name}</span>}
                  </div>
                  <button
                    type="button"
                    className="inline-flex size-7 items-center justify-center rounded-md text-muted transition-colors hover:bg-surface hover:text-danger"
                    aria-label={`Remove ${row.symbol}`}
                    onClick={() => removeSymbol(row.symbol)}
                  >
                    <X className="size-4" aria-hidden />
                  </button>
                </div>
                {row.error ? (
                  <p className="mt-1 text-xs text-danger">{row.error}</p>
                ) : (
                  <>
                    <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-muted">
                      <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-extrabold", actionBadge[row.action])}>
                        {row.action}
                      </span>
                      {row.risk_badge && (
                        <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-extrabold", badgeTone[row.risk_badge] ?? "bg-surface-raised text-muted")}>
                          {row.risk_badge} risk
                        </span>
                      )}
                      {row.portfolio_role && (
                        <span className="font-semibold text-ink">{row.portfolio_role}</span>
                      )}
                      <span>Score {row.score}</span>
                    </div>
                    {row.allocation_size ? (
                      <p className="mt-1 text-[11px] text-muted">
                        Suggested size ≈ {(row.allocation_size * 100).toFixed(0)}% of your shares budget
                      </p>
                    ) : null}
                  </>
                )}
              </div>
            ))}
          </div>

          <div className="mt-3 flex items-start gap-2 rounded-lg border border-amber-400/30 bg-amber-400/5 p-2.5">
            <ShieldAlert className="mt-0.5 size-3.5 shrink-0 text-warning" aria-hidden />
            <p className="text-xs leading-5 text-muted">
              This is a quick health-check of your watchlist, not advice to buy or sell. Want a
              structured starting point instead? <Link className="font-semibold text-focus hover:text-ink" to="/plan">Build a starter plan</Link>.
            </p>
          </div>
        </Card>
      )}

      <Disclaimer compliance={complianceQuery.data} />
    </>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface-raised p-3">
      <div className="text-[11px] text-muted">{label}</div>
      <div className="mt-0.5 text-base font-bold text-ink">{value}</div>
    </div>
  );
}
