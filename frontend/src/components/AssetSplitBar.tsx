import { cn } from "@/lib/cn";
import type { RiskProfile } from "@/types/api";

const ASSET_LABELS: Record<string, string> = {
  equity_delivery: "Shares",
  mutual_funds: "Mutual funds",
  liquid: "Safe & liquid",
};

const PARTS = [
  { key: "equity_delivery", color: "bg-emerald-500" },
  { key: "mutual_funds", color: "bg-sky-500" },
  { key: "liquid", color: "bg-amber-400" },
] as const;

/** Visual split of a risk profile's asset allocation (shares / funds / safe). */
export function AssetSplitBar({ split }: { split: RiskProfile["asset_split"] }) {
  return (
    <div>
      <div className="flex h-3 overflow-hidden rounded-full border border-border">
        {PARTS.map(({ key, color }) => (
          <div key={key} className={color} style={{ width: `${(split[key] ?? 0) * 100}%` }} />
        ))}
      </div>
      <div className="mt-2 grid grid-cols-3 gap-2 text-center text-[11px] text-muted">
        {PARTS.map(({ key, color }) => (
          <div key={key}>
            <span className={cn("mr-1 inline-block size-2 rounded-full", color)} aria-hidden />
            {ASSET_LABELS[key]} {Math.round((split[key] ?? 0) * 100)}%
          </div>
        ))}
      </div>
    </div>
  );
}
