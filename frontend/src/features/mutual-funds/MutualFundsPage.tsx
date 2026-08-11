import { useMutation, useQuery } from "@tanstack/react-query";
import { BarChart3, Calculator, ListFilter, Plus, SlidersHorizontal, X } from "lucide-react";
import { useState } from "react";
import { api } from "@/api/endpoints";
import { Disclaimer } from "@/components/Disclaimer";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { LoadingState } from "@/components/ui/Spinner";
import { controlClass } from "@/components/ui/styles";
import { cn } from "@/lib/cn";
import { fmt, pct } from "@/lib/format";
import type { FundCategory, FundScheme, SipResult } from "@/types/api";

const CATEGORY_OPTIONS: Array<{ value: FundCategory; label: string }> = [
  { value: "large_cap", label: "Large cap" },
  { value: "mid_cap", label: "Mid cap" },
  { value: "small_cap", label: "Small cap" },
  { value: "flexi_cap", label: "Flexi cap" },
  { value: "multi_cap", label: "Multi cap" },
  { value: "value", label: "Value" },
  { value: "elss", label: "ELSS (tax saver)" },
  { value: "index", label: "Index" },
  { value: "liquid", label: "Liquid" },
  { value: "debt", label: "Debt" },
  { value: "hybrid", label: "Hybrid" },
  { value: "other", label: "Other" },
];

const SORT_OPTIONS = [
  { value: "sharpe", label: "Sharpe ratio" },
  { value: "three_year", label: "3-year return" },
  { value: "one_year", label: "1-year return" },
  { value: "expense_ratio", label: "Lowest expense" },
  { value: "aum_cr", label: "AUM" },
];

const RISK_BADGE: Record<number, string> = {
  1: "bg-emerald-500/15 text-brand",
  2: "bg-emerald-500/15 text-brand",
  3: "bg-amber-400/15 text-warning",
  4: "bg-amber-400/15 text-warning",
  5: "bg-rose-500/15 text-danger",
};

type Tab = "screener" | "compare" | "sip";

export default function MutualFundsPage() {
  const [tab, setTab] = useState<Tab>("screener");
  const status = useQuery({ queryKey: ["mutual-fund-status"], queryFn: api.mutualFundStatus });

  return (
    <>
      <PageHeader
        title="Mutual Funds"
        description="Screen direct-plan funds by category, cost and risk-adjusted returns, compare a few side by side, and model a SIP. Data refreshes daily from the AMFI NAV feed."
      />

      {status.data && (
        <Card className="mb-4 border-brand/30 bg-emerald-500/5">
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <span className="font-semibold text-ink">
              {status.data.enabled
                ? `${status.data.universe_size} direct-plan funds loaded`
                : "Mutual-fund data source is disabled"}
            </span>
            <span className="text-xs text-muted">
              {status.data.source} · NAV as of{" "}
              {status.data.data_as_of ? new Date(status.data.data_as_of).toLocaleString() : "—"}
            </span>
          </div>
          {status.data.note && (
            <p className="mt-1.5 text-xs leading-5 text-muted">{status.data.note}</p>
          )}
        </Card>
      )}

      <div className="mb-4 flex flex-wrap gap-2" role="tablist" aria-label="Mutual fund tools">
        {(
          [
            { id: "screener", label: "Screener", icon: SlidersHorizontal },
            { id: "compare", label: "Compare", icon: BarChart3 },
            { id: "sip", label: "SIP calculator", icon: Calculator },
          ] as Array<{ id: Tab; label: string; icon: typeof SlidersHorizontal }>
        ).map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-semibold transition-colors",
              tab === id
                ? "border-brand bg-brand/10 text-ink"
                : "border-border bg-surface-raised text-muted hover:border-muted",
            )}
            onClick={() => setTab(id)}
          >
            <Icon className="size-4" aria-hidden />
            {label}
          </button>
        ))}
      </div>

      {tab === "screener" && <ScreenerTab />}
      {tab === "compare" && <CompareTab />}
      {tab === "sip" && <SipTab />}

      <Disclaimer />
    </>
  );
}

/* ---------------------------------- Screener -------------------------------- */

function ScreenerTab() {
  const [category, setCategory] = useState<string>("");
  const [sortBy, setSortBy] = useState("sharpe");
  const [elssOnly, setElssOnly] = useState(false);
  const [maxRisk, setMaxRisk] = useState("");

  const screener = useQuery({
    queryKey: ["mutual-fund-screener", category, sortBy, elssOnly, maxRisk],
    queryFn: () =>
      api.mutualFundScreener({
        category: category || undefined,
        sort_by: sortBy,
        elss_only: elssOnly || undefined,
        max_risk_rating: maxRisk || undefined,
      }),
  });

  const data = screener.data;

  return (
    <Card>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm font-semibold text-ink">
          Category
          <select className={controlClass} value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">All categories</option>
            {CATEGORY_OPTIONS.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm font-semibold text-ink">
          Sort by
          <select className={controlClass} value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
            {SORT_OPTIONS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm font-semibold text-ink">
          Max risk rating (1–5)
          <select className={controlClass} value={maxRisk} onChange={(e) => setMaxRisk(e.target.value)}>
            <option value="">Any</option>
            <option value="2">2 or below</option>
            <option value="3">3 or below</option>
            <option value="4">4 or below</option>
          </select>
        </label>
        <label className="flex items-center gap-2 pb-2.5 text-sm font-semibold text-ink">
          <input
            type="checkbox"
            className="size-4 accent-brand"
            checked={elssOnly}
            onChange={(e) => setElssOnly(e.target.checked)}
          />
          ELSS (tax saver) only
        </label>
        <Button
          fullWidth={false}
          variant="secondary"
          onClick={() => void screener.refetch()}
          disabled={screener.isFetching}
        >
          <ListFilter className="size-4" aria-hidden />
          Apply
        </Button>
      </div>

      {data && (
        <p className="mt-3 text-xs text-muted">
          {data.total} funds · sorted by {data.sort_by} {data.sort_dir} · NAV as of{" "}
          {data.data_as_of ? new Date(data.data_as_of).toLocaleString() : "—"}
          {data.stale ? " · showing cached data" : ""}
        </p>
      )}

      <div className="mt-4">
        {screener.isLoading ? (
          <LoadingState>Loading funds…</LoadingState>
        ) : screener.isError ? (
          <p className="text-sm text-danger">Could not load funds. Please try again.</p>
        ) : (
          <div className="grid gap-3">
            {data?.items.map((fund) => (
              <FundRow key={fund.scheme_code} fund={fund} />
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}

function FundRow({ fund }: { fund: FundScheme }) {
  const rating = fund.risk.rating ?? null;
  return (
    <div className="rounded-lg border border-border bg-surface-raised p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[15px] font-bold text-ink">
              {fund.fund_house} {fund.scheme_name.replace(/ - Direct Plan.*/, "").replace(/^Direct Plan/, "")}
            </span>
            <span className="text-xs text-muted">#{fund.scheme_code}</span>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px]">
            <span className="rounded-full bg-surface px-2 py-0.5 font-semibold text-muted">
              {CATEGORY_OPTIONS.find((c) => c.value === fund.category)?.label ?? fund.category}
            </span>
            {fund.badges.map((badge) => (
              <span key={badge} className="rounded-full bg-sky-500/15 px-2 py-0.5 font-bold text-sky-600 dark:text-sky-400">
                {badge}
              </span>
            ))}
            {rating != null && (
              <span className={cn("rounded-full px-2 py-0.5 font-bold", RISK_BADGE[rating] ?? "bg-surface text-muted")}>
                Risk {rating}/5
              </span>
            )}
            {fund.expense_ratio != null && (
              <span className="rounded-full bg-surface px-2 py-0.5 text-muted">
                {fund.expense_ratio.toFixed(2)}% expense
              </span>
            )}
          </div>
        </div>
        <div className="text-right">
          <div className="text-sm font-bold text-ink">
            {fund.nav != null ? `₹${fund.nav.toFixed(2)}` : "—"}
          </div>
          <div className="text-[11px] text-muted">NAV</div>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <ReturnStat label="1Y" value={fund.returns.one_year} />
        <ReturnStat label="3Y" value={fund.returns.three_year} />
        <ReturnStat label="5Y" value={fund.returns.five_year} />
        <ReturnStat label="Sharpe" value={fund.risk.sharpe} isRatio />
      </div>
    </div>
  );
}

function ReturnStat({ label, value, isRatio = false }: { label: string; value: number | null; isRatio?: boolean }) {
  return (
    <div className="rounded-lg bg-surface px-2.5 py-2">
      <div className="text-[11px] text-muted">{label}</div>
      <div
        className={cn(
          "text-sm font-bold",
          value == null
            ? "text-muted"
            : isRatio
              ? "text-ink"
              : value >= 0
                ? "text-brand"
                : "text-danger",
        )}
      >
        {value == null ? "—" : isRatio ? value.toFixed(2) : pct(value)}
      </div>
    </div>
  );
}

/* ---------------------------------- Compare -------------------------------- */

function CompareTab() {
  const [codes, setCodes] = useState<number[]>([]);

  const compare = useMutation({
    mutationFn: api.mutualFundCompare,
  });

  const toggleCode = (code: number) => {
    setCodes((prev) =>
      prev.includes(code)
        ? prev.filter((c) => c !== code)
        : prev.length >= 4
          ? prev
          : [...prev, code],
    );
  };

  return (
    <Card>
      <div className="flex items-start gap-2">
        <BarChart3 className="mt-0.5 size-4 shrink-0 text-brand" aria-hidden />
        <CardTitle>Compare up to 4 funds</CardTitle>
      </div>
      <p className="mt-1 text-sm text-muted">
        Pick 2–4 funds from the screener above and compare returns, risk and costs side by side.
        Selected codes are remembered while you stay on this tab.
      </p>

      {codes.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {codes.map((code) => (
            <span
              key={code}
              className="inline-flex items-center gap-1.5 rounded-full border border-brand/40 bg-brand/10 px-2.5 py-1 text-xs font-bold text-ink"
            >
              #{code}
              <button type="button" aria-label={`Remove fund ${code}`} onClick={() => toggleCode(code)}>
                <X className="size-3" aria-hidden />
              </button>
            </span>
          ))}
          <Button
            fullWidth={false}
            disabled={codes.length < 2 || compare.isPending}
            onClick={() => compare.mutate(codes)}
          >
            {compare.isPending ? "Comparing…" : "Compare"}
          </Button>
        </div>
      )}

      {compare.isPending && <LoadingState>Comparing funds…</LoadingState>}

      {compare.isError && (
        <p className="mt-4 text-sm text-danger">Comparison failed. Please try again.</p>
      )}

      {compare.data && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse text-sm">
            <thead>
              <tr>
                <th className="border-b border-border pb-2 text-left text-xs font-bold uppercase text-muted">Fund</th>
                <th className="border-b border-border pb-2 text-right text-xs font-bold uppercase text-muted">NAV</th>
                <th className="border-b border-border pb-2 text-right text-xs font-bold uppercase text-muted">1Y</th>
                <th className="border-b border-border pb-2 text-right text-xs font-bold uppercase text-muted">3Y</th>
                <th className="border-b border-border pb-2 text-right text-xs font-bold uppercase text-muted">5Y</th>
                <th className="border-b border-border pb-2 text-right text-xs font-bold uppercase text-muted">Risk</th>
                <th className="border-b border-border pb-2 text-right text-xs font-bold uppercase text-muted">Sharpe</th>
                <th className="border-b border-border pb-2 text-right text-xs font-bold uppercase text-muted">Expense</th>
                <th className="border-b border-border pb-2 text-right text-xs font-bold uppercase text-muted">AUM</th>
              </tr>
            </thead>
            <tbody>
              {compare.data.schemes.map((fund) => (
                <tr key={fund.scheme_code}>
                  <td className="border-b border-border/60 py-2.5 pr-2">
                    <span className="font-semibold text-ink">
                      {fund.fund_house} {fund.scheme_name.replace(/ - Direct Plan.*/, "")}
                    </span>
                    <span className="block text-[11px] text-muted">
                      {CATEGORY_OPTIONS.find((c) => c.value === fund.category)?.label ?? fund.category} · #{fund.scheme_code}
                    </span>
                  </td>
                  <td className="border-b border-border/60 py-2.5 text-right font-semibold text-ink">
                    {fund.nav != null ? `₹${fund.nav.toFixed(2)}` : "—"}
                  </td>
                  <td className="border-b border-border/60 py-2.5 text-right text-brand">
                    {fund.returns.one_year != null ? pct(fund.returns.one_year) : "—"}
                  </td>
                  <td className="border-b border-border/60 py-2.5 text-right text-brand">
                    {fund.returns.three_year != null ? pct(fund.returns.three_year) : "—"}
                  </td>
                  <td className="border-b border-border/60 py-2.5 text-right text-brand">
                    {fund.returns.five_year != null ? pct(fund.returns.five_year) : "—"}
                  </td>
                  <td className="border-b border-border/60 py-2.5 text-right">
                    {fund.risk.rating != null ? (
                      <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-bold", RISK_BADGE[fund.risk.rating])}>
                        {fund.risk.rating}/5
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="border-b border-border/60 py-2.5 text-right text-ink">
                    {fund.risk.sharpe != null ? fund.risk.sharpe.toFixed(2) : "—"}
                  </td>
                  <td className="border-b border-border/60 py-2.5 text-right text-ink">
                    {fund.expense_ratio != null ? `${fund.expense_ratio.toFixed(2)}%` : "—"}
                  </td>
                  <td className="border-b border-border/60 py-2.5 text-right text-ink">
                    {fund.aum_cr != null ? `₹${fmt(fund.aum_cr / 1000, 1)}k Cr` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-[11px] text-muted">
            Expense ratio and AUM are curated approximations refreshed periodically. Returns are
            historical, not a forecast.
          </p>
        </div>
      )}

      <div className="mt-4">
        <div className="mb-1.5 text-xs font-bold uppercase text-muted">How to add funds</div>
        <p className="text-sm leading-6 text-muted">
          Go to the Screener tab, note the fund numbers you like, then type them here separated by
          commas (2–4 funds).
        </p>
        <ManualCodeEntry onAdd={toggleCode} disabled={codes.length >= 4} />
      </div>
    </Card>
  );
}

function ManualCodeEntry({ onAdd, disabled }: { onAdd: (code: number) => void; disabled: boolean }) {
  const [raw, setRaw] = useState("");
  const add = () => {
    const code = Number.parseInt(raw.replace(/\D/g, ""), 10);
    if (!Number.isNaN(code) && code > 0 && !disabled) {
      onAdd(code);
      setRaw("");
    }
  };
  return (
    <div className="mt-2 flex items-center gap-2">
      <input
        className={controlClass}
        inputMode="numeric"
        placeholder="e.g. 122639"
        value={raw}
        onChange={(e) => setRaw(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") add();
        }}
      />
      <Button fullWidth={false} variant="secondary" onClick={add} disabled={disabled}>
        <Plus className="size-4" aria-hidden />
        Add
      </Button>
    </div>
  );
}

/* ------------------------------------- SIP ---------------------------------- */

function SipTab() {
  const [mode, setMode] = useState<"sip" | "lumpsum" | "sip_stepup">("sip");
  const [monthly, setMonthly] = useState("10000");
  const [lumpsum, setLumpsum] = useState("100000");
  const [years, setYears] = useState("10");
  const [returnPct, setReturnPct] = useState("12");
  const [stepUp, setStepUp] = useState("10");

  const result = useMutation({
    mutationFn: api.mutualFundSip,
  });

  const run = () => {
    const parsedMonthly = parseFloat(monthly.replace(/[₹,\s]/g, "")) || 0;
    const parsedLumpsum = parseFloat(lumpsum.replace(/[₹,\s]/g, "")) || 0;
    const parsedYears = Number.parseInt(years, 10) || 10;
    const parsedReturn = parseFloat(returnPct) || 0;
    const parsedStep = parseFloat(stepUp) || 0;
    result.mutate({
      mode,
      monthly_amount: mode === "lumpsum" ? undefined : parsedMonthly,
      lumpsum_amount: mode === "lumpsum" ? parsedLumpsum : undefined,
      years: parsedYears,
      assumed_return_pct: parsedReturn,
      step_up_pct: mode === "sip_stepup" ? parsedStep : undefined,
    });
  };

  const out = result.data;

  return (
    <Card>
      <div className="flex items-start gap-2">
        <Calculator className="mt-0.5 size-4 shrink-0 text-brand" aria-hidden />
        <CardTitle>SIP / lumpsum calculator</CardTitle>
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label className="grid gap-1.5 text-sm font-semibold text-ink">
          Mode
          <select className={controlClass} value={mode} onChange={(e) => setMode(e.target.value as typeof mode)}>
            <option value="sip">Monthly SIP</option>
            <option value="sip_stepup">Monthly SIP with yearly step-up</option>
            <option value="lumpsum">One-time lumpsum</option>
          </select>
        </label>
        {mode === "lumpsum" ? (
          <label className="grid gap-1.5 text-sm font-semibold text-ink">
            Lumpsum amount (₹)
            <input className={controlClass} inputMode="numeric" value={lumpsum} onChange={(e) => setLumpsum(e.target.value)} />
          </label>
        ) : (
          <label className="grid gap-1.5 text-sm font-semibold text-ink">
            Monthly amount (₹)
            <input className={controlClass} inputMode="numeric" value={monthly} onChange={(e) => setMonthly(e.target.value)} />
          </label>
        )}
        <label className="grid gap-1.5 text-sm font-semibold text-ink">
          Years
          <input className={controlClass} inputMode="numeric" value={years} onChange={(e) => setYears(e.target.value)} />
        </label>
        <label className="grid gap-1.5 text-sm font-semibold text-ink">
          Assumed yearly return (%)
          <input className={controlClass} inputMode="numeric" value={returnPct} onChange={(e) => setReturnPct(e.target.value)} />
        </label>
        {mode === "sip_stepup" && (
          <label className="grid gap-1.5 text-sm font-semibold text-ink">
            Yearly step-up (%)
            <input className={controlClass} inputMode="numeric" value={stepUp} onChange={(e) => setStepUp(e.target.value)} />
          </label>
        )}
      </div>

      <Button className="mt-3" onClick={run} disabled={result.isPending}>
        {result.isPending ? "Calculating…" : "Calculate"}
      </Button>

      {result.isError && (
        <p className="mt-3 text-sm text-danger">Calculation failed. Check your inputs.</p>
      )}

      {out && <SipResultView out={out} />}
    </Card>
  );
}

function SipResultView({ out }: { out: SipResult }) {
  return (
    <div className="mt-4 grid gap-3 sm:grid-cols-2">
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-lg border border-border bg-surface-raised p-3">
          <div className="text-[11px] text-muted">Total invested</div>
          <div className="mt-0.5 text-base font-bold text-ink">₹{out.invested.toLocaleString("en-IN")}</div>
        </div>
        <div className="rounded-lg border border-brand/40 bg-brand/10 p-3">
          <div className="text-[11px] text-muted">Projected value</div>
          <div className="mt-0.5 text-base font-bold text-brand">
            ₹{Math.round(out.future_value).toLocaleString("en-IN")}
          </div>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[280px] border-collapse text-sm">
          <thead>
            <tr>
              <th className="border-b border-border pb-1.5 text-left text-xs font-bold uppercase text-muted">Year</th>
              <th className="border-b border-border pb-1.5 text-right text-xs font-bold uppercase text-muted">Invested</th>
              <th className="border-b border-border pb-1.5 text-right text-xs font-bold uppercase text-muted">Value</th>
            </tr>
          </thead>
          <tbody>
            {out.table.map((row) => (
              <tr key={row.year}>
                <td className="border-b border-border/60 py-1.5 font-semibold text-ink">{row.year}</td>
                <td className="border-b border-border/60 py-1.5 text-right text-muted">
                  ₹{Math.round(row.invested).toLocaleString("en-IN")}
                </td>
                <td className="border-b border-border/60 py-1.5 text-right font-semibold text-brand">
                  ₹{Math.round(row.value).toLocaleString("en-IN")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] leading-5 text-muted sm:col-span-2">
        Assumed {out.assumed_return_pct}% yearly return. SIP projections are illustrative, not a
        promise of returns.
      </p>
    </div>
  );
}
