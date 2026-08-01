import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { LoadingState } from "@/components/ui/Spinner";
import type { IndianRecord, IndianSnapshot, IndianStock } from "@/types/api";
import { RefreshCw, Search, TrendingDown, TrendingUp } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  useIndianOverview,
  useIndianSearch,
  useIndianStock,
  useIndianStockData,
} from "./hooks/useIndianMarket";

function asRecords(value: IndianSnapshot | unknown): IndianRecord[] {
  if (Array.isArray(value))
    return value.filter((item): item is IndianRecord => typeof item === "object" && item !== null);
  if (value && typeof value === "object") return [value as IndianRecord];
  return [];
}

function trendingRows(value: IndianSnapshot | unknown): IndianRecord[] {
  const rows = asRecords(value);
  if (rows.length !== 1) return rows;
  const trending = rows[0].trending_stocks;
  if (!trending || typeof trending !== "object" || Array.isArray(trending)) return rows;
  const groups = trending as IndianRecord;
  return [...asRecords(groups.top_gainers), ...asRecords(groups.top_losers)];
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function useDebouncedValue(value: string, delay = 350): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [delay, value]);
  return debounced;
}

function SnapshotCard({
  title,
  value,
  icon: Icon,
  records = asRecords,
}: {
  title: string;
  value: unknown;
  icon: typeof TrendingUp;
  records?: (value: unknown) => IndianRecord[];
}) {
  const rows = records(value);
  return (
    <Card>
      <CardTitle className="flex items-center gap-2 text-base">
        <Icon className="size-4 text-brand" aria-hidden />
        {title}
      </CardTitle>
      {rows.length ? (
        <ul className="mt-3 space-y-2 text-sm">
          {rows.slice(0, 5).map((row, index) => {
            const label =
              row.name ??
              row.companyName ??
              row.commonName ??
              row.symbol ??
              row.tickerId ??
              `Item ${index + 1}`;
            const numeric = row.percentChange ?? row.change ?? row.currentPrice ?? row.price;
            return (
              <li
                key={`${String(label)}-${index}`}
                className="flex justify-between gap-3 border-b border-border/60 pb-2 last:border-0"
              >
                <span className="truncate text-ink">{displayValue(label)}</span>
                <span className="shrink-0 font-semibold text-muted">{displayValue(numeric)}</span>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-muted">No data available right now.</p>
      )}
    </Card>
  );
}

function Chart({ points }: { points: IndianRecord[] }) {
  const values = points
    .map((point) => Number(point.close ?? point.price ?? point.value ?? point.last ?? NaN))
    .filter(Number.isFinite);
  if (values.length < 2)
    return (
      <p className="text-sm text-muted">Historical prices are not available for this selection.</p>
    );
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const path = values
    .map(
      (value, index) =>
        `${index ? "L" : "M"}${(index / (values.length - 1)) * 100},${100 - ((value - min) / span) * 90 - 5}`,
    )
    .join(" ");
  return (
    <svg
      viewBox="0 0 100 100"
      className="h-56 w-full overflow-visible"
      role="img"
      aria-label="Historical price chart"
      preserveAspectRatio="none"
    >
      <path
        d={path}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
        className="text-brand"
      />
    </svg>
  );
}

export default function IndianMarketPage() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<"stock" | "industry" | "mutual-fund">("stock");
  const [stockId, setStockId] = useState("");
  const [period, setPeriod] = useState("1y");
  const debouncedQuery = useDebouncedValue(query);
  const overview = useIndianOverview();
  const stock = useIndianStock(mode === "stock" ? debouncedQuery : "");
  const discovery = useIndianSearch(
    mode === "stock" ? "" : debouncedQuery,
    mode === "mutual-fund" ? "mutual-fund" : "industry",
  );
  const data = useIndianStockData(stockId, period, "");
  const stockData = stock.data?.data as IndianStock | undefined;
  const snapshots = useMemo(() => overview.data?.data.snapshots ?? {}, [overview.data]);
  const refresh = () => {
    void overview.refetch();
    if (stockId) {
      void data.history.refetch();
      void data.stats.refetch();
    }
  };

  const openSelection = () => {
    if (mode !== "stock") return;
    const nextStockId = stockData?.ticker_id || query.trim();
    if (nextStockId) setStockId(nextStockId);
  };

  return (
    <>
      <PageHeader
        title="Indian Market"
        description="Explore Indian market snapshots and provider-backed company analysis. Market data is informational, not investment advice."
      />
      <Card className="border-brand/30 bg-emerald-500/5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <label className="min-w-0 flex-1 text-sm font-semibold text-ink">
            Search market data
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Reliance, banking, mutual fund…"
              className="mt-1 min-h-11 w-full rounded-lg border border-border bg-surface px-3 text-ink outline-none focus:border-focus"
            />
          </label>
          <label className="text-sm font-semibold text-ink">
            Type
            <select
              value={mode}
              onChange={(event) => setMode(event.target.value as typeof mode)}
              className="mt-1 min-h-11 rounded-lg border border-border bg-surface px-3 text-ink"
            >
              <option value="stock">Company</option>
              <option value="industry">Industry</option>
              <option value="mutual-fund">Mutual fund</option>
            </select>
          </label>
          <Button
            fullWidth={false}
            variant="secondary"
            onClick={openSelection}
            disabled={mode !== "stock" || (!query.trim() && !stockData?.ticker_id)}
          >
            <Search className="size-4" aria-hidden />
            Open
          </Button>
          <Button
            fullWidth={false}
            variant="secondary"
            onClick={refresh}
            aria-label="Refresh Indian market data"
          >
            <RefreshCw className="size-4" aria-hidden />
          </Button>
        </div>
        {((mode === "stock" && stock.isFetching) ||
          (mode !== "stock" && discovery.isFetching)) && (
          <p className="mt-3 text-sm text-muted" role="status" aria-live="polite">
            Searching…
          </p>
        )}
        {mode !== "stock" && discovery.data?.data && (
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {discovery.data.data.slice(0, 8).map((item, index) => (
              <button
                key={index}
                type="button"
                className="rounded-lg border border-border bg-surface p-3 text-left text-sm text-ink hover:border-focus"
                onClick={() => {
                  setQuery(
                    displayValue(item.name ?? item.companyName ?? item.commonName ?? item.symbol),
                  );
                }}
              >
                {displayValue(item.name ?? item.companyName ?? item.commonName ?? item.symbol)}
                <span className="block text-xs text-muted">
                  {displayValue(
                    item.id ?? item.tickerId ?? item.exchangeCodeNsi ?? item.exchangeCodeBse ?? item.code,
                  )}
                </span>
              </button>
            ))}
          </div>
        )}
        {mode !== "stock" &&
          !discovery.isFetching &&
          debouncedQuery &&
          discovery.data?.data?.length === 0 && (
            <p className="mt-3 text-sm text-muted">
              No matching {mode === "industry" ? "industries" : "mutual funds"} found.
            </p>
          )}
        {stock.isError && (
          <p className="mt-3 text-sm text-danger">
            Company lookup failed. The provider may be disabled or unavailable.
          </p>
        )}
      </Card>

      {overview.isLoading ? (
        <LoadingState>Loading market overview…</LoadingState>
      ) : overview.isError ? (
        <Card>
          <p className="text-sm text-danger">
            Market overview is unavailable. Check the provider configuration or try again later.
          </p>
        </Card>
      ) : (
        <>
          {(overview.data?.warnings?.length ?? 0) > 0 && (
            <Card className="border-amber-500/40 bg-amber-500/5" role="status">
              <p className="text-sm font-semibold text-ink">Some market data may be incomplete</p>
              <ul className="mt-1 list-disc pl-5 text-xs text-muted">
                {overview.data?.warnings?.map((warning) => <li key={warning}>{warning}</li>)}
              </ul>
            </Card>
          )}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <SnapshotCard
              title="Top movers"
              value={snapshots.trending}
              icon={TrendingUp}
              records={trendingRows}
            />
            <SnapshotCard
              title="Most active NSE"
              value={snapshots.nse_most_active}
              icon={TrendingUp}
            />
            <SnapshotCard
              title="Most active BSE"
              value={snapshots.bse_most_active}
              icon={TrendingDown}
            />
            <SnapshotCard
              title="Price shockers"
              value={snapshots.price_shockers}
              icon={TrendingDown}
            />
          </div>
          <p className="mb-3 text-xs text-muted">
            Source: {overview.data?.provider ?? "Indian market provider"} · As of{" "}
            {overview.data?.fetched_at ? new Date(overview.data.fetched_at).toLocaleString() : "—"}
            {overview.data?.stale ? " · Showing cached data" : ""}
          </p>
        </>
      )}

      {stockData && (
        <>
          <Card>
            <CardTitle>{stockData.company_name || stockData.ticker_id}</CardTitle>
            <div className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              <div>
                <span className="block text-muted">Ticker</span>
                <strong>{stockData.ticker_id}</strong>
              </div>
              <div>
                <span className="block text-muted">NSE / BSE</span>
                <strong>
                  {Object.entries(stockData.current_price)
                    .map(([key, value]) => `${key}: ${value}`)
                    .join(" · ") || "—"}
                </strong>
              </div>
              <div>
                <span className="block text-muted">Change</span>
                <strong
                  className={
                    stockData.percent_change && stockData.percent_change >= 0
                      ? "text-brand"
                      : "text-danger"
                  }
                >
                  {displayValue(stockData.percent_change)}%
                </strong>
              </div>
              <div>
                <span className="block text-muted">Year range</span>
                <strong>
                  {displayValue(stockData.year_low)} – {displayValue(stockData.year_high)}
                </strong>
              </div>
            </div>
            <p className="mt-3 text-sm text-muted">
              {stockData.industry || "Industry unavailable"} · Informational data only.
            </p>
          </Card>
          <div className="grid gap-3 lg:grid-cols-2">
          <Card>
              <div className="flex items-center justify-between">
                <CardTitle>Price history</CardTitle>
                <select
                  value={period}
                  onChange={(event) => setPeriod(event.target.value)}
                  className="rounded-lg border border-border bg-surface px-2 py-1 text-sm text-ink"
                >
                  <option value="1m">1 month</option>
                  <option value="6m">6 months</option>
                  <option value="1y">1 year</option>
                  <option value="5y">5 years</option>
                </select>
              </div>
              {data.history.isLoading ? (
                <LoadingState>Loading chart…</LoadingState>
              ) : (
                <Chart points={data.history.data?.data.points ?? []} />
              )}
            </Card>
            <Card>
              <CardTitle>Historical stats</CardTitle>
              {data.stats.isLoading ? (
                <LoadingState>Loading stats…</LoadingState>
            ) : (
                <pre className="mt-3 max-h-56 overflow-auto whitespace-pre-wrap text-xs text-muted">
                  {JSON.stringify(data.stats.data?.data.stats ?? {}, null, 2)}
              </pre>
            )}
          </Card>
          </div>
          <div className="grid gap-3 lg:grid-cols-2">
            <Card>
              <CardTitle>Analyst recommendations</CardTitle>
              {data.recommendations.isLoading ? <LoadingState>Loading recommendations…</LoadingState> : data.recommendations.isError ? (
                <p className="mt-3 text-sm text-muted">Recommendations are unavailable for this stock.</p>
              ) : <pre className="mt-3 max-h-48 overflow-auto whitespace-pre-wrap text-xs text-muted">{JSON.stringify(data.recommendations.data?.data ?? "No recommendation data", null, 2)}</pre>}
            </Card>
            <Card>
              <CardTitle>Forecasts</CardTitle>
              {data.forecasts.isLoading ? <LoadingState>Loading forecasts…</LoadingState> : data.forecasts.isError ? (
                <p className="mt-3 text-sm text-muted">Forecasts are unavailable for this stock.</p>
              ) : <pre className="mt-3 max-h-48 overflow-auto whitespace-pre-wrap text-xs text-muted">{JSON.stringify(data.forecasts.data?.data ?? "No forecast data", null, 2)}</pre>}
            </Card>
          </div>
        </>
      )}
    </>
  );
}
