import type { ScanRow } from "@/types/api";
import { fmt, pct, stripExchangeSuffix } from "@/lib/format";
import styles from "./RecommendationCard.module.css";

export function RecommendationCard({ row }: { row: ScanRow }) {
  if (row.error) {
    return (
      <div className={styles.card}>
        <div className={styles.sym}>{row.symbol}</div>
        <div className={styles.meta}>Error: {row.error}</div>
      </div>
    );
  }

  const actionClass = row.action.toLowerCase();
  const showLevels = row.action === "BUY" || row.action === "SELL";

  return (
    <div className={`${styles.card} ${styles[actionClass] ?? ""}`}>
      <div className={styles.cardHead}>
        <div>
          <div className={styles.sym}>{stripExchangeSuffix(row.symbol)}</div>
          <div className={styles.name}>
            {row.name}
            {row.sector ? ` · ${row.sector}` : ""}
          </div>
        </div>
        <div className={`${styles.badge} ${styles[row.action]}`}>{row.action}</div>
      </div>

      <div className={styles.score}>
        Score {row.score > 0 ? "+" : ""}
        {fmt(row.score, 0)}
        {row.rr ? ` · R:R ${fmt(row.rr, 2)}` : ""}
      </div>

      <div className={styles.priceLine}>
        LTP <b>₹{fmt(row.price)}</b>
      </div>

      {showLevels && (
        <div className={styles.grid3}>
          <div className={styles.kv}>
            <div className="k">Entry</div>
            <div className="v">₹{fmt(row.entry)}</div>
          </div>
          <div className={styles.kv}>
            <div className="k">Target</div>
            <div className="v">₹{fmt(row.target)}</div>
          </div>
          <div className={styles.kv}>
            <div className="k">Stop-loss</div>
            <div className="v">₹{fmt(row.stop_loss)}</div>
          </div>
        </div>
      )}

      <div className={styles.meta}>
        RSI {fmt(row.rsi, 1)} · SMA50 {fmt(row.sma50, 1)} · SMA200 {fmt(row.sma200, 1)} · PE{" "}
        {fmt(row.pe, 1)} · PEG {fmt(row.peg, 2)} · ROE {pct(row.roe)}
      </div>

      {row.reasons && row.reasons.length > 0 && (
        <ul className={styles.reasons}>
          {row.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
