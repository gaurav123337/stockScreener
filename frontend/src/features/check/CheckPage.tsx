import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/endpoints";
import { Section } from "@/components/Section";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { controlClass, labelClass } from "@/components/ui/styles";
import { LoadingState } from "@/components/ui/Spinner";
import { CheckCircle2, ExternalLink, ShieldAlert, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import type { CheckBeforeBuy } from "@/types/api";

const LEVEL_STYLES: Record<string, string> = {
  green: "border-emerald-500/40 bg-emerald-500/5",
  amber: "border-amber-500/40 bg-amber-500/5",
  red: "border-rose-500/40 bg-rose-500/5",
  info: "border-border bg-surface-raised",
};

const LEVEL_ICONS: Record<string, typeof CheckCircle2> = {
  green: CheckCircle2,
  amber: ShieldAlert,
  red: ShieldAlert,
  info: ShieldCheck,
};

export default function CheckPage() {
  const [symbol, setSymbol] = useState("");
  const [submitted, setSubmitted] = useState("");

  const checkQuery = useQuery({
    queryKey: ["check", submitted],
    queryFn: () => api.checkBeforeBuy(submitted),
    enabled: Boolean(submitted),
  });
  const brokersQuery = useQuery({ queryKey: ["check", "brokers"], queryFn: api.checkBrokers });

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const value = symbol.trim().toUpperCase();
    if (!value) return;
    setSubmitted(value);
  };

  const result: CheckBeforeBuy | undefined = checkQuery.data;

  return (
    <>
      <Section
        title="Check before you buy"
        sub="A pre-trade review: is the price fair, is the plan intact, and how big should the position be? stockScreener is research — you place the order yourself in your own broker app."
      />

      <Card className="p-5">
        <form onSubmit={handleSubmit} className="grid gap-3 sm:grid-cols-[1fr_auto]">
          <label className={labelClass}>
            Symbol
            <input
              className={controlClass}
              value={symbol}
              onChange={(event) => setSymbol(event.target.value)}
              placeholder="e.g. RELIANCE"
            />
          </label>
          <Button className="sm:w-auto sm:self-end" disabled={!symbol.trim()}>
            Run checklist
          </Button>
        </form>
      </Card>

      {checkQuery.isPending && submitted ? (
        <LoadingState />
      ) : checkQuery.isError ? (
        <p className="py-6 text-center text-sm text-muted">No checklist available for that symbol.</p>
      ) : result ? (
        <Card
          className={
            "p-5 " +
            (result.verdict === "green"
              ? "border-emerald-500/40"
              : "border-amber-500/40")
          }
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-bold text-ink">
              {result.symbol} · ₹{result.price.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
            </h2>
            <span
              className={
                "rounded-full px-2.5 py-1 text-xs font-bold uppercase tracking-wide " +
                (result.verdict === "green"
                  ? "bg-emerald-500/15 text-emerald-600"
                  : "bg-amber-500/15 text-amber-600")
              }
            >
              {result.verdict === "green" ? "Looks reasonable" : "Review carefully"}
            </span>
          </div>
          <p className="mt-1 text-xs text-muted">
            {result.action} · score {result.score.toFixed(1)} · risk {result.risk_badge}
          </p>

          <div className="mt-4 grid gap-2">
            {result.items.map((item) => {
              const Icon = LEVEL_ICONS[item.level] ?? CheckCircle2;
              return (
                <div key={item.title} className={"rounded-panel border p-3 " + LEVEL_STYLES[item.level]}>
                  <div className="flex items-center justify-between gap-2">
                    <p className="flex items-center gap-1.5 text-sm font-bold text-ink">
                      <Icon className="size-4 shrink-0" aria-hidden />
                      {item.title}
                    </p>
                    <p className="text-right text-xs font-semibold text-muted">{item.text}</p>
                  </div>
                  <p className="mt-1 text-xs leading-5 text-muted">{item.guidance}</p>
                </div>
              );
            })}
          </div>

          <div className="mt-4">
            <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted">
              Review in your broker app
            </p>
            <div className="flex flex-wrap gap-2">
              {(brokersQuery.data?.brokers ?? []).map((broker) => (
                <a
                  key={broker.id}
                  href="#"
                  onClick={(event) => {
                    event.preventDefault();
                    void api.checkDeepLink(broker.id, result.symbol).then((link) => {
                      window.open(link.web, "_blank", "noopener,noreferrer");
                    });
                  }}
                  className="inline-flex items-center gap-1 rounded-panel border border-border bg-surface-raised px-3 py-2 text-xs font-semibold text-ink hover:border-focus"
                >
                  {broker.name}
                  <ExternalLink className="size-3.5" aria-hidden />
                </a>
              ))}
            </div>
            <p className="mt-1.5 text-[11px] leading-4 text-muted">
              Deep-links open the symbol for review only. stockScreener never places orders.
            </p>
          </div>

          <p className="mt-4 text-[11px] leading-4 text-muted">{result.disclaimer}</p>
        </Card>
      ) : (
        <p className="py-6 text-center text-sm text-muted">
          Enter a symbol to review it before you buy.
        </p>
      )}
    </>
  );
}
