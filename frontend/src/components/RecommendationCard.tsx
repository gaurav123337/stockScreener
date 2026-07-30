import { cn } from "@/lib/cn";
import { fmt, pct, stripExchangeSuffix } from "@/lib/format";
import type { ScanRow } from "@/types/api";

const actionStyles: Record<string, { border: string; badge: string }> = {
  BUY: { border: "border-l-4 border-l-emerald-500", badge: "bg-emerald-500/15 text-brand" },
  SELL: { border: "border-l-4 border-l-rose-500", badge: "bg-rose-500/15 text-danger" },
  HOLD: { border: "border-l-4 border-l-yellow-400", badge: "bg-yellow-400/15 text-warning" },
};

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
        <div
          className={cn(
            "whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-extrabold",
            actionStyle.badge,
          )}
        >
          {row.action}
        </div>
      </div>

      <div className="mt-0.5 text-xs text-muted">
        Score {row.score > 0 ? "+" : ""}
        {fmt(row.score, 0)}
        {row.rr ? ` · R:R ${fmt(row.rr, 2)}` : ""}
      </div>

      <div className="mt-2 mb-1 text-[15px]">
        LTP <b>₹{fmt(row.price)}</b>
      </div>

      {showLevels && (
        <div className="my-2.5 grid grid-cols-3 gap-2">
          <div className="rounded-lg border border-border bg-surface-raised p-2">
            <div className="text-[11px] text-muted">Entry</div>
            <div className="mt-0.5 text-sm font-bold">₹{fmt(row.entry)}</div>
          </div>
          <div className="rounded-lg border border-border bg-surface-raised p-2">
            <div className="text-[11px] text-muted">Target</div>
            <div className="mt-0.5 text-sm font-bold">₹{fmt(row.target)}</div>
          </div>
          <div className="rounded-lg border border-border bg-surface-raised p-2">
            <div className="text-[11px] text-muted">Stop-loss</div>
            <div className="mt-0.5 text-sm font-bold">₹{fmt(row.stop_loss)}</div>
          </div>
        </div>
      )}

      <div className="my-2 text-xs text-muted">
        RSI {fmt(row.rsi, 1)} · SMA50 {fmt(row.sma50, 1)} · SMA200 {fmt(row.sma200, 1)} · PE{" "}
        {fmt(row.pe, 1)} · PEG {fmt(row.peg, 2)} · ROE {pct(row.roe)}
      </div>

      {row.reasons && row.reasons.length > 0 && (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-[13px] text-ink">
          {row.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
