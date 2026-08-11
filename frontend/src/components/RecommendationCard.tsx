import { AlertTriangle, ChevronDown } from "lucide-react";
import { useState } from "react";
import { GlossaryTooltip } from "@/components/GlossaryTooltip";
import { cn } from "@/lib/cn";
import { fmt, pct, stripExchangeSuffix } from "@/lib/format";
import type { DriverScore, ScanRow } from "@/types/api";

const actionStyles: Record<string, { border: string; badge: string }> = {
  BUY: { border: "border-l-4 border-l-emerald-500", badge: "bg-emerald-500/15 text-brand" },
  SELL: { border: "border-l-4 border-l-rose-500", badge: "bg-rose-500/15 text-danger" },
  HOLD: { border: "border-l-4 border-l-yellow-400", badge: "bg-yellow-400/15 text-warning" },
};

const badgeTone: Record<string, string> = {
  Low: "bg-emerald-500/15 text-brand",
  Medium: "bg-amber-400/15 text-warning",
  High: "bg-rose-500/15 text-danger",
};

function driverTone(driver: DriverScore): string {
  if (driver.positive === true) return "text-brand";
  if (driver.positive === false) return "text-danger";
  return "text-muted";
}

function DriverRow({ driver }: { driver: DriverScore }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-lg border border-border bg-surface-raised p-2.5">
      <button
        type="button"
        className="flex w-full items-center gap-2 text-left focus-visible:outline-none"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
      >
        <span
          className={cn(
            "inline-flex h-6 min-w-12 items-center justify-center rounded-md px-1.5 text-xs font-extrabold",
            driver.positive === true && "bg-emerald-500/15",
            driver.positive === false && "bg-rose-500/15",
            driver.positive === null && "bg-surface text-muted",
            driverTone(driver),
          )}
        >
          {driver.positive === null ? "–" : driver.positive ? "+" : ""}
          {fmt(driver.score, 0)}
        </span>
        <span className="text-sm font-bold text-ink">{driver.label}</span>
        <ChevronDown
          aria-hidden="true"
          className={cn("ml-auto size-4 shrink-0 text-muted transition-transform", open && "rotate-180")}
        />
      </button>
      <p className="mt-1.5 text-xs leading-5 text-muted">{driver.plain}</p>
      {open && driver.why.length > 0 && (
        <ul className="mt-1.5 list-disc space-y-1 pl-5 text-xs leading-5 text-muted">
          {driver.why.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function RecommendationCard({ row }: { row: ScanRow }) {
  if (row.error) {
    return (
      <div className="mb-3 rounded-panel border border-rose-500/40 bg-surface p-3.5">
        <div className="text-[17px] font-bold">{row.symbol}</div>
        <div className="mt-2 text-xs text-danger">Error: {row.error}</div>
      </div>
    );
  }

  const actionStyle = actionStyles[row.action] ?? actionStyles.HOLD;
  const showLevels = row.action === "BUY" || row.action === "SELL";
  const drivers = row.drivers ?? [];
  const hasThesis = Boolean(row.thesis || drivers.length > 0);

  return (
    <div
      className={cn("mb-3 rounded-panel border border-border bg-surface p-3.5", actionStyle.border)}
    >
      <div className="flex items-baseline justify-between gap-2">
        <div>
          <div className="text-[17px] font-bold">{stripExchangeSuffix(row.symbol)}</div>
          <div className="text-xs text-muted">
            {row.name}
            {row.sector ? ` · ${row.sector}` : ""}
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          {row.risk_badge && (
            <span
              className={cn(
                "whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-extrabold",
                badgeTone[row.risk_badge] ?? "bg-surface-raised text-muted",
              )}
            >
              {row.risk_badge} risk
            </span>
          )}
          <div
            className={cn(
              "whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-extrabold",
              actionStyle.badge,
            )}
          >
            {row.action}
          </div>
        </div>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
        <GlossaryTooltip term="score">
          <span className="font-semibold">
            Score {row.score > 0 ? "+" : ""}
            {fmt(row.score, 0)}
          </span>
        </GlossaryTooltip>
        {row.confidence !== null && row.confidence !== undefined && (
          <GlossaryTooltip term="confidence">
            <span className="font-semibold">Confidence {(row.confidence * 100).toFixed(0)}%</span>
          </GlossaryTooltip>
        )}
        {row.rr ? (
          <GlossaryTooltip term="rr">
            <span>R:R {fmt(row.rr, 2)}</span>
          </GlossaryTooltip>
        ) : null}
        {row.portfolio_role && <span className="font-semibold text-ink">{row.portfolio_role}</span>}
        {row.allocation_size ? (
          <GlossaryTooltip term="weight">
            <span>Suggested size ≈ {(row.allocation_size * 100).toFixed(0)}% of shares</span>
          </GlossaryTooltip>
        ) : null}
      </div>

      {hasThesis && (
        <>
          {row.thesis && <p className="mt-2.5 text-sm leading-6 text-ink">{row.thesis}</p>}

          {drivers.length > 0 && (
            <div className="mt-3 grid gap-2 md:grid-cols-2">
              {drivers.map((driver) => (
                <DriverRow key={driver.key} driver={driver} />
              ))}
            </div>
          )}

          {row.what_could_go_wrong && row.what_could_go_wrong.length > 0 && (
            <div className="mt-3 rounded-lg border border-amber-400/30 bg-amber-400/5 p-2.5">
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-warning" aria-hidden />
                <div>
                  <div className="text-xs font-bold uppercase text-warning">What could go wrong</div>
                  <ul className="mt-1 list-disc space-y-1 pl-4 text-xs leading-5 text-muted">
                    {row.what_could_go_wrong.map((risk) => (
                      <li key={risk}>{risk}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      <div className="mt-2 mb-1 text-[15px]">
        <GlossaryTooltip term="entry">
          <span>
            LTP <b>₹{fmt(row.price)}</b>
          </span>
        </GlossaryTooltip>
      </div>

      {showLevels && (
        <div className="my-2.5 grid grid-cols-3 gap-2">
          <div className="rounded-lg border border-border bg-surface-raised p-2">
            <GlossaryTooltip term="entry">
              <div className="text-[11px] text-muted">Entry</div>
            </GlossaryTooltip>
            <div className="mt-0.5 text-sm font-bold">₹{fmt(row.entry)}</div>
          </div>
          <div className="rounded-lg border border-border bg-surface-raised p-2">
            <GlossaryTooltip term="target">
              <div className="text-[11px] text-muted">Target</div>
            </GlossaryTooltip>
            <div className="mt-0.5 text-sm font-bold">₹{fmt(row.target)}</div>
          </div>
          <div className="rounded-lg border border-border bg-surface-raised p-2">
            <GlossaryTooltip term="stop_loss">
              <div className="text-[11px] text-muted">Stop-loss</div>
            </GlossaryTooltip>
            <div className="mt-0.5 text-sm font-bold">₹{fmt(row.stop_loss)}</div>
          </div>
        </div>
      )}

      <div className="my-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">
        {row.rsi !== null && row.rsi !== undefined && (
          <GlossaryTooltip term="rsi">
            <span>RSI {fmt(row.rsi, 1)}</span>
          </GlossaryTooltip>
        )}
        {row.sma50 !== null && row.sma50 !== undefined && (
          <GlossaryTooltip term="sma50">
            <span>SMA50 {fmt(row.sma50, 1)}</span>
          </GlossaryTooltip>
        )}
        {row.sma200 !== null && row.sma200 !== undefined && (
          <GlossaryTooltip term="sma200">
            <span>SMA200 {fmt(row.sma200, 1)}</span>
          </GlossaryTooltip>
        )}
        {row.pe !== null && row.pe !== undefined && (
          <GlossaryTooltip term="pe">
            <span>P/E {fmt(row.pe, 1)}</span>
          </GlossaryTooltip>
        )}
        {row.peg !== null && row.peg !== undefined && (
          <GlossaryTooltip term="peg">
            <span>PEG {fmt(row.peg, 2)}</span>
          </GlossaryTooltip>
        )}
        {row.roe !== null && row.roe !== undefined && (
          <GlossaryTooltip term="roe">
            <span>ROE {pct(row.roe)}</span>
          </GlossaryTooltip>
        )}
      </div>

      {!hasThesis && row.reasons && row.reasons.length > 0 && (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-[13px] text-ink">
          {row.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
