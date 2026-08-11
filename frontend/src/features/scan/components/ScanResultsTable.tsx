import { cn } from "@/lib/cn";
import { fmt, pct, stripExchangeSuffix } from "@/lib/format";
import type { ScanResponse, ScanRow } from "@/types/api";

const HEADINGS = [
  "Symbol",
  "Action",
  "Score",
  "Price",
  "Target",
  "Stop",
  "R:R",
  "RSI",
  "PE",
  "ROE",
];
const tableCellClass = "whitespace-nowrap border-b border-border px-3 py-2.5 text-right";
const actionTextStyles: Record<string, string> = {
  BUY: "font-bold text-brand",
  SELL: "font-bold text-danger",
  HOLD: "font-bold text-warning",
};

export function ScanResultsTable(props: {
  result: ScanResponse;
  openRow: number | null;
  onToggleRow: (index: number) => void;
}) {
  const { result, openRow, onToggleRow } = props;
  if (!result.results.length) {
    return <div className="px-6 py-8 text-center text-sm text-muted">No matches.</div>;
  }

  return (
    <>
      <div className="mt-4 overflow-x-auto rounded-panel border border-border bg-surface">
        <table className="w-full border-collapse text-[13px]">
          <thead>
            <tr className="bg-surface-raised text-xs text-muted">
              {HEADINGS.map((heading, index) => (
                <th
                  key={heading}
                  className={cn(
                    tableCellClass,
                    "font-semibold",
                    index === 0 && "sticky left-0 z-10 bg-surface-raised text-left",
                  )}
                >
                  {heading}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.results.map((row, index) => (
              <ScanResultRows
                key={row.symbol}
                row={row}
                open={openRow === index}
                onToggle={() => onToggleRow(index)}
              />
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-2 space-y-1 text-xs leading-5 text-muted">
        <p>
          {result.count} matched · {result.failed.length} failed to fetch. Select a row for reasons.
        </p>
        {(typeof result.universe_size === "number" ||
          result.data_updated_at ||
          result.data_source) && (
          <p>
            {typeof result.coverage === "number" && result.universe_size > 0 && (
              <>Coverage {Math.round(result.coverage * 100)}% of {result.universe_size} symbols · </>
            )}
            {result.data_source ? <>{result.data_source} </> : null}
            {result.data_updated_at ? <>As of {fmtDate(result.data_updated_at)}.</> : null}
          </p>
        )}
        {result.stale && (
          <p className="font-semibold text-warning">
            Data may be stale — last fetch is older than the cache window.
          </p>
        )}
      </div>
    </>
  );
}

function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: "short",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

function ScanResultRows({
  row,
  open,
  onToggle,
}: {
  row: ScanRow;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <tr
        className={cn(
          "cursor-pointer transition-colors hover:bg-surface-raised",
          open && "bg-surface-raised",
        )}
        onClick={onToggle}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            onToggle();
          }
        }}
        tabIndex={0}
        aria-expanded={open}
      >
        <td className={cn(tableCellClass, "sticky left-0 z-10 bg-surface text-left font-semibold")}>
          <span className={cn("mr-1 inline-block transition-transform", open && "rotate-90")}>
            ▸
          </span>{" "}
          {stripExchangeSuffix(row.symbol)}
        </td>
        <td className={cn(tableCellClass, actionTextStyles[row.action])}>{row.action}</td>
        <td className={tableCellClass}>
          {row.score > 0 ? "+" : ""}
          {fmt(row.score, 0)}
        </td>
        <td className={tableCellClass}>{fmt(row.price, 1)}</td>
        <td className={tableCellClass}>{fmt(row.target, 1)}</td>
        <td className={tableCellClass}>{fmt(row.stop_loss, 1)}</td>
        <td className={tableCellClass}>{row.rr ? fmt(row.rr, 2) : "-"}</td>
        <td className={tableCellClass}>{fmt(row.rsi, 0)}</td>
        <td className={tableCellClass}>{fmt(row.pe, 1)}</td>
        <td className={tableCellClass}>{pct(row.roe)}</td>
      </tr>
      {open && (
        <tr className="bg-canvas/50">
          <td className="border-b border-border px-4 py-3" colSpan={10}>
            {row.reasons?.length ? (
              <ul className="list-disc space-y-1 pl-5 text-sm text-ink">
                {row.reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-muted">No specific reasons — mixed/neutral signals.</p>
            )}
          </td>
        </tr>
      )}
    </>
  );
}
