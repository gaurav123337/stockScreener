import { Check, ChevronDown, ChevronUp, SlidersHorizontal } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { controlClass } from "@/components/ui/styles";
import { cn } from "@/lib/cn";
import type { PredefinedFilter } from "@/types/api";

interface ScanControlsProps {
  symbols: string;
  selectedFilter: string;
  customFilter: string;
  top: string;
  filters: PredefinedFilter[];
  isScanning: boolean;
  onSymbolsChange: (value: string) => void;
  onFilterChange: (value: string) => void;
  onCustomFilterChange: (value: string) => void;
  onTopChange: (value: string) => void;
  onRun: () => void;
}

const chipClass =
  "inline-flex min-h-9 items-center gap-1.5 rounded-full border-2 px-3 py-1.5 text-xs font-semibold shadow-sm transition-colors hover:border-brand hover:text-ink";

function FilterChip(props: {
  active: boolean;
  label: string;
  title?: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={cn(
        chipClass,
        props.active
          ? "border-brand bg-brand text-emerald-950 shadow-md shadow-emerald-950/20"
          : "border-border bg-surface text-muted",
      )}
      title={props.title}
      aria-pressed={props.active}
      onClick={props.onClick}
    >
      {props.active && <Check aria-hidden="true" className="size-3.5 stroke-[3]" />}
      {props.label}
    </button>
  );
}

export function ScanControls(props: ScanControlsProps) {
  const {
    symbols,
    selectedFilter,
    customFilter,
    top,
    filters,
    isScanning,
    onSymbolsChange,
    onFilterChange,
    onCustomFilterChange,
    onTopChange,
    onRun,
  } = props;

  const [advanced, setAdvanced] = useState(false);

  const guided = filters.filter((f) => f.guided);
  const technical = filters.filter((f) => !f.guided);

  return (
    <>
      <div className="my-3">
        <div className="mb-1.5 text-xs font-bold uppercase text-muted">What do you want?</div>
        <div className="flex flex-wrap gap-2" aria-label="Guided filters">
          <FilterChip active={!selectedFilter} label="Everything" onClick={() => onFilterChange("")} />
          {guided.map((filter) => (
            <FilterChip
              key={filter.name}
              active={selectedFilter === filter.name}
              label={filter.name === "stable_companies" ? "Stable companies" : filter.name === "tax_saving" ? "Save tax" : "Growth"}
              title={filter.description}
              onClick={() => onFilterChange(filter.name)}
            />
          ))}
        </div>
      </div>

      <button
        type="button"
        className="mt-1 inline-flex items-center gap-1.5 text-xs font-semibold text-focus transition-colors hover:text-ink"
        aria-expanded={advanced}
        onClick={() => setAdvanced((current) => !current)}
      >
        <SlidersHorizontal className="size-3.5" aria-hidden />
        {advanced ? "Hide" : "Show"} advanced filters
        {advanced ? <ChevronUp className="size-3.5" aria-hidden /> : <ChevronDown className="size-3.5" aria-hidden />}
      </button>

      {advanced && (
        <div className="mt-3 grid gap-3">
          <input
            className={controlClass}
            type="text"
            placeholder="Symbols (blank = Nifty 50) e.g. RELIANCE TCS"
            value={symbols}
            onChange={(event) => onSymbolsChange(event.target.value)}
          />
          <div>
            <div className="mb-1.5 text-xs font-bold uppercase text-muted">Technical screens</div>
            <div className="flex flex-wrap gap-2" aria-label="Technical filters">
              {technical.map((filter) => (
                <FilterChip
                  key={filter.name}
                  active={selectedFilter === filter.name}
                  label={filter.name}
                  title={filter.description}
                  onClick={() => onFilterChange(filter.name)}
                />
              ))}
            </div>
          </div>
          <input
            className={controlClass}
            type="text"
            placeholder="Custom filter e.g. rsi < 35 and roe > 0.15 (overrides chips)"
            value={customFilter}
            onChange={(event) => onCustomFilterChange(event.target.value)}
          />
          <input
            className={cn(controlClass, "max-w-36")}
            type="text"
            placeholder="Top N (optional)"
            inputMode="numeric"
            value={top}
            onChange={(event) => onTopChange(event.target.value)}
          />
        </div>
      )}

      <div className="mt-3">
        <Button onClick={onRun} disabled={isScanning}>
          {isScanning ? "Scanning…" : "Run scan"}
        </Button>
      </div>
    </>
  );
}
