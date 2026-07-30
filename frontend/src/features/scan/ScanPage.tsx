import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/api/endpoints";
import { useToast } from "@/app/useToast";
import { Section } from "@/components/Section";
import { LoadingState } from "@/components/ui/Spinner";
import type { ScanResponse } from "@/types/api";
import { ScanControls } from "./components/ScanControls";
import { ScanResultsTable } from "./components/ScanResultsTable";
import { StockAutocomplete } from "./components/StockAutocomplete";
import { useStockAutocomplete } from "./hooks/useStockAutocomplete";

function parseSymbols(raw: string): string[] {
  return raw.split(/[\s,]+/).filter(Boolean);
}

export default function ScanPage() {
  const { toast } = useToast();
  const filtersQuery = useQuery({ queryKey: ["filters"], queryFn: api.filters });
  const autocomplete = useStockAutocomplete();
  const [symbols, setSymbols] = useState("");
  const [selectedFilter, setSelectedFilter] = useState("");
  const [customFilter, setCustomFilter] = useState("");
  const [top, setTop] = useState("");
  const [result, setResult] = useState<ScanResponse | null>(null);
  const [openRow, setOpenRow] = useState<number | null>(null);

  const addSymbol = (symbol: string) => {
    const tokens = parseSymbols(symbols.trim());
    if (!tokens.map((t) => t.toUpperCase()).includes(symbol.toUpperCase())) {
      tokens.push(symbol);
    }
    setSymbols(tokens.join(" "));
    autocomplete.setSearch("");
    autocomplete.setIsOpen(false);
  };

  const scanMutation = useMutation({
    mutationFn: api.scan,
    onSuccess: (res) => {
      setResult(res);
      setOpenRow(null);
    },
    onError: (e) => {
      setResult(null);
      toast(e instanceof Error ? e.message : "Scan failed");
    },
  });

  const runScan = () => {
    const syms = parseSymbols(symbols.trim());
    const whereClause = customFilter.trim() || null;
    const topN = parseInt(top, 10) || null;
    scanMutation.mutate({
      symbols: syms.length ? syms : null,
      filter: whereClause ? null : selectedFilter || null,
      where: whereClause,
      top: topN,
    });
  };

  return (
    <>
      <Section title="Scan" sub="Screen Nifty 50 (or your list) with a filter, ranked by score." />

      <StockAutocomplete
        value={autocomplete.search}
        results={autocomplete.results}
        isOpen={autocomplete.isOpen}
        containerRef={autocomplete.containerRef}
        onChange={autocomplete.setSearch}
        onSelect={addSymbol}
        onClose={() => autocomplete.setIsOpen(false)}
      />
      <ScanControls
        symbols={symbols}
        selectedFilter={selectedFilter}
        customFilter={customFilter}
        top={top}
        filters={filtersQuery.data?.predefined ?? []}
        isScanning={scanMutation.isPending}
        onSymbolsChange={setSymbols}
        onFilterChange={setSelectedFilter}
        onCustomFilterChange={setCustomFilter}
        onTopChange={setTop}
        onRun={runScan}
      />

      {scanMutation.isPending && <LoadingState>Scanning… (live data, may take a bit)</LoadingState>}

      {!scanMutation.isPending && result && (
        <ScanResultsTable
          result={result}
          openRow={openRow}
          onToggleRow={(index) => setOpenRow(openRow === index ? null : index)}
        />
      )}
    </>
  );
}
