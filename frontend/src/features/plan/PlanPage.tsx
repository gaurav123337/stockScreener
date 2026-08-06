import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, RefreshCw, ShieldQuestion, Sparkles, Target } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/api/endpoints";
import { useToast } from "@/app/useToast";
import { AssetSplitBar } from "@/components/AssetSplitBar";
import { Disclaimer } from "@/components/Disclaimer";
import { Section } from "@/components/Section";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { LoadingState } from "@/components/ui/Spinner";
import { controlClass } from "@/components/ui/styles";
import { cn } from "@/lib/cn";
import { pct } from "@/lib/format";
import type { InvestmentPlan } from "@/types/api";

const GOALS: Array<{ value: string; label: string }> = [
  { value: "wealth", label: "Build wealth over the long term" },
  { value: "retirement", label: "Save for retirement / financial freedom" },
  { value: "tax", label: "Save tax (like an ELSS fund)" },
  { value: "goal", label: "A specific goal (education, a house)" },
];

const HORIZONS: Array<{ value: number; label: string }> = [
  { value: 3, label: "About 3 years" },
  { value: 5, label: "About 5 years" },
  { value: 10, label: "About 10 years" },
  { value: 15, label: "15 years or more" },
];

const badgeTone: Record<string, string> = {
  Low: "bg-emerald-500/15 text-brand",
  Medium: "bg-amber-400/15 text-warning",
  High: "bg-rose-500/15 text-danger",
};

export default function PlanPage() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const complianceQuery = useQuery({ queryKey: ["compliance"], queryFn: api.compliance });
  const profileQuery = useQuery({ queryKey: ["risk-profile"], queryFn: api.getRiskProfile });

  const profile = profileQuery.data;
  const profileLevel = profile?.level;

  const [goal, setGoal] = useState("wealth");
  const [amount, setAmount] = useState("10000");
  const [horizon, setHorizon] = useState(10);
  const [plan, setPlan] = useState<InvestmentPlan | null>(null);

  const buildMutation = useMutation({
    mutationFn: api.buildPlan,
    onSuccess: setPlan,
    onError: (e) => toast(e instanceof Error ? e.message : "Could not build your plan"),
  });

  if (profileQuery.isLoading) {
    return <LoadingState>Loading your profile…</LoadingState>;
  }

  if (!profileLevel) {
    return (
      <>
        <Section
          title="Your starter plan"
          sub="A simple, diversified starting point built around your goals."
        />
        <Card>
          <div className="flex items-start gap-2">
            <Target className="mt-0.5 size-4 shrink-0 text-brand" aria-hidden />
            <CardTitle>Let&apos;s set up your plan first</CardTitle>
          </div>
          <p className="mt-2 text-sm leading-6 text-muted">
            Answer five quick questions about your goals, time frame and comfort with ups and
            downs. We&apos;ll then recommend a mix of shares, mutual funds and safer options that
            suits you.
          </p>
          <div className="mt-4">
            <Button onClick={() => navigate("/onboarding")}>
              Start the 5-minute setup <ArrowRight className="size-4" aria-hidden />
            </Button>
          </div>
        </Card>
      </>
    );
  }

  const run = () => {
    const parsed = parseFloat(amount.replace(/[₹,\s]/g, "")) || 0;
    buildMutation.mutate({ risk_level: profileLevel, monthly_amount: parsed, horizon_years: horizon, goal });
  };

  const displayPlan = plan;
  const amountLabel = displayPlan ? `₹${displayPlan.monthly_amount.toLocaleString("en-IN")}` : "";

  return (
    <>
      <Section
        title="Your starter plan"
        sub={`A ${displayPlan?.risk_label.toLowerCase() ?? "moderate"} plan built for your goals — 3–5 simple holdings with reasons, rebalanced quarterly.`}
      />

      {!displayPlan && (
        <Card>
          <div className="flex items-start gap-2">
            <Sparkles className="mt-0.5 size-4 shrink-0 text-brand" aria-hidden />
            <CardTitle>Tell us about your plan</CardTitle>
          </div>
          <div className="mt-3 grid gap-3">
            <label className="grid gap-1.5 text-sm font-semibold text-ink">
              Your main goal
              <select
                className={controlClass}
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
              >
                {GOALS.map((g) => (
                  <option key={g.value} value={g.value}>
                    {g.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="grid gap-1.5 text-sm font-semibold text-ink">
              How much can you invest each month?
              <input
                className={controlClass}
                type="text"
                inputMode="numeric"
                placeholder="e.g. 10000"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
              />
            </label>
            <label className="grid gap-1.5 text-sm font-semibold text-ink">
              How long will you keep this money invested?
              <div className="grid grid-cols-2 gap-2">
                {HORIZONS.map((h) => (
                  <button
                    key={h.value}
                    type="button"
                    className={cn(
                      "rounded-lg border px-3 py-2.5 text-sm font-semibold transition-colors",
                      horizon === h.value
                        ? "border-brand bg-brand/10 text-ink"
                        : "border-border bg-surface-raised text-muted hover:border-muted",
                    )}
                    aria-pressed={horizon === h.value}
                    onClick={() => setHorizon(h.value)}
                  >
                    {h.label}
                  </button>
                ))}
              </div>
            </label>
            <Button onClick={run} disabled={buildMutation.isPending}>
              {buildMutation.isPending ? "Building your plan…" : "Build my plan"}
            </Button>
          </div>
        </Card>
      )}

      {buildMutation.isPending && !displayPlan && (
        <LoadingState>Scoring a diversified basket of large companies…</LoadingState>
      )}

      {displayPlan && (
        <>
          <Card>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex items-start gap-2">
                  <Sparkles className="mt-0.5 size-4 shrink-0 text-brand" aria-hidden />
                  <CardTitle>Your {displayPlan.risk_label} plan</CardTitle>
                </div>
                <p className="mt-1 text-xs text-muted">
                  {amountLabel} a month for about {displayPlan.horizon_years} years.
                </p>
              </div>
              <Button
                variant="secondary"
                fullWidth={false}
                onClick={run}
                disabled={buildMutation.isPending}
              >
                <RefreshCw className="size-4" aria-hidden />
                Refresh
              </Button>
            </div>

            <div className="mt-4">
              <div className="mb-1.5 text-xs font-bold uppercase text-muted">Where your money goes</div>
              <AssetSplitBar split={displayPlan.asset_split} />
            </div>

            <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-4">
              <Stat label="Expected yearly return" value={`${pct(displayPlan.expected_return_range[0])}–${pct(displayPlan.expected_return_range[1])}`} />
              <Stat label="Conservative estimate" value={`${pct(displayPlan.conservative_return_range[0])}–${pct(displayPlan.conservative_return_range[1])}`} />
              <Stat label="Shares part" value={pct(displayPlan.asset_split.equity_delivery ?? 0)} />
              <Stat label="Funds + safe part" value={pct((displayPlan.asset_split.mutual_funds ?? 0) + (displayPlan.asset_split.liquid ?? 0))} />
            </div>
          </Card>

          <Card>
            <div className="flex items-start gap-2">
              <Target className="mt-0.5 size-4 shrink-0 text-brand" aria-hidden />
              <CardTitle>Your starter basket of shares</CardTitle>
            </div>
            <p className="mt-1 text-xs text-muted">
              Picked by the same engine that powers every recommendation, spread across sectors.
              Percentages below are the share of your <strong>shares budget</strong>, not your whole
              money.
            </p>
            <div className="mt-3 grid gap-3">
              {displayPlan.basket.map((item) => (
                <div
                  key={item.symbol}
                  className="rounded-lg border border-border bg-surface-raised p-3"
                >
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <div>
                      <span className="text-[15px] font-bold text-ink">{item.name ?? item.symbol}</span>
                      <span className="ml-1.5 text-xs text-muted">{item.symbol}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-extrabold", badgeTone[item.risk_badge ?? ""] ?? "bg-surface text-muted")}>
                        {item.risk_badge ?? "—"} risk
                      </span>
                      <span className="text-sm font-bold text-brand">{pct(item.weight)}</span>
                    </div>
                  </div>
                  <div className="mt-1 text-xs text-muted">{item.sector}</div>
                  <p className="mt-2 text-[13px] leading-5 text-ink">{item.plain}</p>
                  {item.driver_highlights.length > 0 && (
                    <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-muted">
                      {item.driver_highlights.map((line) => (
                        <li key={line}>{line}</li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          </Card>

          <Card>
            <div className="flex items-start gap-2">
              <ShieldQuestion className="mt-0.5 size-4 shrink-0 text-muted" aria-hidden />
              <CardTitle>Mutual-fund suggestions</CardTitle>
            </div>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-muted">
              {displayPlan.mutual_funds.map((fund) => (
                <li key={fund}>{fund}</li>
              ))}
            </ul>
          </Card>

          <Card>
            <div className="flex items-start gap-2">
              <RefreshCw className="mt-0.5 size-4 shrink-0 text-muted" aria-hidden />
              <CardTitle>Keep it on track</CardTitle>
            </div>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-muted">
              {displayPlan.notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </Card>
        </>
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
