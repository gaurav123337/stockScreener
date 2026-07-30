import { Check } from "lucide-react";
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

  return (
    <>
      <input
        className={cn(controlClass, "mt-2")}
        type="text"
        placeholder="Symbols (blank = Nifty 50) e.g. RELIANCE TCS"
        value={symbols}
        onChange={(event) => onSymbolsChange(event.target.value)}
      />
      <div className="my-3 flex flex-wrap gap-2" aria-label="Predefined filters">
        <FilterChip active={!selectedFilter} label="All" onClick={() => onFilterChange("")} />
        {filters.map((filter) => (
          <FilterChip
            key={filter.name}
            active={selectedFilter === filter.name}
            label={filter.name}
            title={filter.description}
            onClick={() => onFilterChange(filter.name)}
          />
        ))}
      </div>
      <input
        className={controlClass}
        type="text"
        placeholder="Custom filter e.g. rsi < 35 and roe > 0.15 (overrides chips)"
        value={customFilter}
        onChange={(event) => onCustomFilterChange(event.target.value)}
      />
      <div className="mt-3 flex items-stretch gap-3">
        <input
          className={cn(controlClass, "max-w-36")}
          type="text"
          placeholder="Top N (optional)"
          inputMode="numeric"
          value={top}
          onChange={(event) => onTopChange(event.target.value)}
        />
        <Button className="flex-1" onClick={onRun} disabled={isScanning}>
          Run scan
        </Button>
      </div>
    </>
  );
}

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
