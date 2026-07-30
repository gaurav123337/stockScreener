import { controlClass } from "@/components/ui/styles";
import { stripExchangeSuffix } from "@/lib/format";
import type { SearchResult } from "@/types/api";
import type { RefObject } from "react";

interface StockAutocompleteProps {
  value: string;
  results: SearchResult[] | null;
  isOpen: boolean;
  containerRef: RefObject<HTMLDivElement>;
  onChange: (value: string) => void;
  onSelect: (symbol: string) => void;
  onClose: () => void;
}

export function StockAutocomplete(props: StockAutocompleteProps) {
  const { value, results, isOpen, containerRef, onChange, onSelect, onClose } = props;

  return (
    <div className="relative" ref={containerRef}>
      <input
        className={controlClass}
        type="search"
        placeholder="Find a stock by name or symbol (e.g. Tata, HDFC, M&M)…"
        autoComplete="off"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            if (results?.[0]) onSelect(results[0].symbol);
          }
          if (event.key === "Escape") onClose();
        }}
      />
      {isOpen && (
        <div className="absolute inset-x-0 top-[calc(100%+0.25rem)] z-20 max-h-72 overflow-y-auto rounded-panel border border-border bg-surface-raised p-1 shadow-panel">
          {results?.length ? (
            results.map((result) => (
              <button
                type="button"
                key={`${result.symbol}-${result.exchange}`}
                className="flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2.5 text-left hover:bg-slate-700/60"
                onClick={() => onSelect(result.symbol)}
              >
                <span>
                  <strong className="block text-sm">{stripExchangeSuffix(result.symbol)}</strong>
                  <span className="block text-xs text-muted">{result.name}</span>
                </span>
                <span className="rounded-md bg-canvas px-2 py-1 text-[11px] font-semibold text-muted">
                  {result.exchange}
                </span>
              </button>
            ))
          ) : (
            <div className="px-3 py-4 text-center text-sm text-muted">
              No matches for "{value.trim()}"
            </div>
          )}
        </div>
      )}
    </div>
  );
}
