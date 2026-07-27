/** Number / percent formatting helpers (ported from the vanilla app). */

export function fmt(n: number | null | undefined | string, digits = 2): string {
  if (n === null || n === undefined || n === "") return "-";
  const num = Number(n);
  if (Number.isNaN(num)) return "-";
  return num.toFixed(digits);
}

export function pct(n: number | null | undefined): string {
  if (n === null || n === undefined) return "-";
  return `${(n * 100).toFixed(0)}%`;
}

/** "RELIANCE.NS" -> "RELIANCE" */
export function stripExchangeSuffix(symbol: string): string {
  return symbol.replace(/\.(NS|BO)$/, "");
}
