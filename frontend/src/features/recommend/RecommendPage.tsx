import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/api/endpoints";
import { useToast } from "@/app/useToast";
import { Section } from "@/components/Section";
import { RecommendationCard } from "@/components/RecommendationCard";
import { Button } from "@/components/ui/Button";
import { LoadingState } from "@/components/ui/Spinner";
import { controlClass } from "@/components/ui/styles";
import type { ScanRow } from "@/types/api";

function parseSymbols(raw: string): string[] {
  return raw.split(/[\s,]+/).filter(Boolean);
}

export default function RecommendPage() {
  const { toast } = useToast();
  const [input, setInput] = useState("");
  const [rows, setRows] = useState<ScanRow[]>([]);

  const mutation = useMutation({
    mutationFn: async (symbols: string[]) => {
      // Per-symbol failures render as error cards, matching the legacy app.
      return Promise.all(
        symbols.map((s) =>
          api.recommend(s).catch((e: unknown): ScanRow => {
            const message = e instanceof Error ? e.message : "Request failed";
            return {
              symbol: s,
              name: null,
              sector: null,
              action: "HOLD",
              score: 0,
              price: null,
              entry: null,
              target: null,
              stop_loss: null,
              rr: null,
              rsi: null,
              sma50: null,
              sma200: null,
              pe: null,
              peg: null,
              roe: null,
              reasons: null,
              error: message,
            };
          }),
        ),
      );
    },
    onSuccess: setRows,
    onError: (e) => toast(e instanceof Error ? e.message : "Failed"),
  });

  const run = () => {
    const symbols = parseSymbols(input.trim());
    if (symbols.length === 0) {
      toast("Enter at least one symbol");
      return;
    }
    mutation.mutate(symbols);
  };

  return (
    <>
      <Section title="Recommend" sub="Buy/Sell/Hold with entry, target, stop-loss and reasons." />

      <div className="grid gap-3">
        <input
          className={controlClass}
          type="text"
          placeholder="Symbols e.g. RELIANCE TCS SBIN"
          autoComplete="off"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && run()}
        />
        <Button onClick={run} disabled={mutation.isPending}>
          Get recommendation
        </Button>
      </div>

      {mutation.isPending ? (
        <LoadingState>Analysing…</LoadingState>
      ) : (
        <div className="mt-4">
          {rows.map((row, i) => (
            <RecommendationCard key={`${row.symbol}-${i}`} row={row} />
          ))}
        </div>
      )}
    </>
  );
}
