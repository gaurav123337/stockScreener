import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/api/endpoints";
import { useToast } from "@/app/useToast";
import { Section } from "@/components/Section";
import { fmt, pct, stripExchangeSuffix } from "@/lib/format";
import type { ScanResponse, SearchResult } from "@/types/api";
import styles from "./ScanPage.module.css";

function parseSymbols(raw: string): string[] {
  return raw.split(/[\s,]+/).filter(Boolean);
}

export default function ScanPage() {
  const { toast } = useToast();

  const filtersQuery = useQuery({ queryKey: ["filters"], queryFn: api.filters });

  const [search, setSearch] = useState("");
  const [acResults, setAcResults] = useState<SearchResult[] | null>(null);
  const [acOpen, setAcOpen] = useState(false);
  const [symbols, setSymbols] = useState("");
  const [chosenFilter, setChosenFilter] = useState("");
  const [where, setWhere] = useState("");
  const [top, setTop] = useState("");
  const [result, setResult] = useState<ScanResponse | null>(null);
  const [openRow, setOpenRow] = useState<number | null>(null);

  const acWrapRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounced stock-search autocomplete (ported from the legacy app).
  useEffect(() => {
    const q = search.trim();
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (q.length < 2) {
      setAcOpen(false);
      setAcResults(null);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      try {
        const res = await api.search(q);
        setAcResults(res.results ?? []);
        setAcOpen(true);
      } catch {
        /* autocomplete errors are non-fatal */
      }
    }, 220);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [search]);

  // Close autocomplete when clicking outside.
  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (acWrapRef.current && !acWrapRef.current.contains(e.target as Node)) {
        setAcOpen(false);
      }
    };
    document.addEventListener("click", onDocClick);
    return () => document.removeEventListener("click", onDocClick);
  }, []);

  const addSymbol = (symbol: string) => {
    const tokens = parseSymbols(symbols.trim());
    if (!tokens.map((t) => t.toUpperCase()).includes(symbol.toUpperCase())) {
      tokens.push(symbol);
    }
    setSymbols(tokens.join(" "));
    setSearch("");
    setAcOpen(false);
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
    const whereClause = where.trim() || null;
    const topN = parseInt(top, 10) || null;
    scanMutation.mutate({
      symbols: syms.length ? syms : null,
      filter: whereClause ? null : chosenFilter || null,
      where: whereClause,
      top: topN,
    });
  };

  const predefined = filtersQuery.data?.predefined ?? [];

  return (
    <>
      <Section
        title="Scan"
        sub="Screen Nifty 50 (or your list) with a filter, ranked by score."
      />

      <div className={styles.acWrap} ref={acWrapRef}>
        <input
          type="text"
          placeholder="🔍 Find a stock by name or symbol (e.g. Tata, HDFC, M&M)…"
          autoComplete="off"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              const first = acResults?.[0];
              if (first) addSymbol(first.symbol);
            }
            if (e.key === "Escape") setAcOpen(false);
          }}
        />
        {acOpen && (
          <div className={styles.acList}>
            {acResults && acResults.length > 0 ? (
              acResults.map((r) => (
                <button
                  key={`${r.symbol}-${r.exchange}`}
                  className={styles.acItem}
                  onClick={() => addSymbol(r.symbol)}
                >
                  <div>
                    <div className={styles.acSym}>{stripExchangeSuffix(r.symbol)}</div>
                    <div className={styles.acName}>{r.name}</div>
                  </div>
                  <span className={styles.acEx}>{r.exchange}</span>
                </button>
              ))
            ) : (
              <div className={styles.acEmpty}>No matches for "{search.trim()}"</div>
            )}
          </div>
        )}
      </div>

      <div style={{ height: 8 }} />
      <input
        type="text"
        placeholder="Symbols (blank = Nifty 50) e.g. RELIANCE TCS"
        value={symbols}
        onChange={(e) => setSymbols(e.target.value)}
      />

      <div className={styles.chipRow}>
        <button
          className={`${styles.chip}${chosenFilter === "" ? ` ${styles.active}` : ""}`}
          onClick={() => setChosenFilter("")}
        >
          All
        </button>
        {predefined.map((f) => (
          <button
            key={f.name}
            className={`${styles.chip}${chosenFilter === f.name ? ` ${styles.active}` : ""}`}
            title={f.desc}
            onClick={() => setChosenFilter(f.name)}
          >
            {f.name}
          </button>
        ))}
      </div>

      <input
        type="text"
        placeholder="Custom filter e.g. rsi < 35 and roe > 0.15 (overrides chips)"
        value={where}
        onChange={(e) => setWhere(e.target.value)}
      />

      <div style={{ height: 10 }} />
      <div className="row">
        <input
          type="text"
          placeholder="Top N (optional)"
          inputMode="numeric"
          style={{ flex: "0 0 120px" }}
          value={top}
          onChange={(e) => setTop(e.target.value)}
        />
        <button className="btn" onClick={runScan} disabled={scanMutation.isPending}>
          Run Scan
        </button>
      </div>

      <div style={{ height: 14 }} />

      {scanMutation.isPending && (
        <div className="center">
          <span className="spinner" /> Scanning… (live data, may take a bit)
        </div>
      )}

      {!scanMutation.isPending && result && (
        <>
          {result.results.length === 0 ? (
            <div className="center">No matches.</div>
          ) : (
            <>
              <div className={styles.tblWrap}>
                <table className={styles.tbl}>
                  <thead>
                    <tr>
                      <th>Symbol</th>
                      <th>Action</th>
                      <th>Score</th>
                      <th>Price</th>
                      <th>Target</th>
                      <th>Stop</th>
                      <th>R:R</th>
                      <th>RSI</th>
                      <th>PE</th>
                      <th>ROE</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.results.map((r, i) => (
                      <ScanResultRows
                        key={r.symbol}
                        row={r}
                        open={openRow === i}
                        onToggle={() => setOpenRow(openRow === i ? null : i)}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="mini" style={{ marginTop: 8 }}>
                {result.count} matched · {result.failed.length} failed to fetch. Tap a row for
                reasons.
              </div>
            </>
          )}
        </>
      )}
    </>
  );
}

function ScanResultRows({
  row,
  open,
  onToggle,
}: {
  row: ScanResponse["results"][number];
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <tr className={`${styles.rowbtn}${open ? ` ${styles.open}` : ""}`} onClick={onToggle}>
        <td>
          <span className={styles.caret}>▸</span> {stripExchangeSuffix(row.symbol)}
        </td>
        <td className={styles[`t${row.action}`]}>{row.action}</td>
        <td>
          {row.score > 0 ? "+" : ""}
          {fmt(row.score, 0)}
        </td>
        <td>{fmt(row.price, 1)}</td>
        <td>{fmt(row.target, 1)}</td>
        <td>{fmt(row.stop_loss, 1)}</td>
        <td>{row.rr ? fmt(row.rr, 2) : "-"}</td>
        <td>{fmt(row.rsi, 0)}</td>
        <td>{fmt(row.pe, 1)}</td>
        <td>{pct(row.roe)}</td>
      </tr>
      {open && (
        <tr className={styles.detail}>
          <td colSpan={10}>
            {row.reasons && row.reasons.length > 0 ? (
              <ul className={styles.reasons}>
                {row.reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            ) : (
              <div className="mini">No specific reasons — mixed/neutral signals.</div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}
