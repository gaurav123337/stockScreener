"""stockScreener CLI — Indian market (NSE/BSE).

Commands:
  recommend SYMBOL [SYMBOL...]   Buy/Sell/Hold with entry, target, stop & reasons
  scan [--filter NAME | --where "EXPR"] [--symbols ...] [--top N]
  filters                        List pre-defined filters
  learn                          Ingest PDFs/notes from knowledge/ into the KB
  verify                         Score past predictions that came due
"""
from __future__ import annotations

import argparse
import sys

# Make stdout tolerant of unicode (₹, —) on legacy Windows consoles
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from rich.console import Console

from rich.table import Table
from rich.panel import Panel
from rich import box

from screener import data, filters as F, knowledge, verify as V
from screener.indicators import add_all
from screener.signals import analyze
from screener.universe import NIFTY50

# ASCII-only output so panels/tables render cleanly on legacy Windows consoles
console = Console(safe_box=True)
ASCII_BOX = box.ASCII
DISCLAIMER = "[dim]Educational tool - not SEBI-registered investment advice. Do your own research.[/dim]"





# --------------------------------------------------------------------------- #
def _scan_row(symbol: str) -> dict | None:
    sd = data.fetch_history(symbol, period="1y")
    if not sd.ok:
        return {"symbol": symbol.upper(), "error": sd.error}
    info = data.fetch_info(symbol)
    rec = analyze(sd.symbol, sd.history, info)
    df = add_all(sd.history)
    last = df.iloc[-1]
    price = rec.price
    row = {
        "symbol": sd.symbol, "name": (rec.metrics.get("name") or "")[:28],
        "action": rec.action, "score": rec.score, "price": price,
        "target": rec.target, "stop_loss": rec.stop_loss, "rr": rec.risk_reward,
        "rsi": rec.metrics.get("rsi"), "pe": rec.metrics.get("pe"),
        "peg": rec.metrics.get("peg"), "roe": rec.metrics.get("roe"),
        "debt_to_equity": rec.metrics.get("debt_to_equity"),
        "sma50": rec.metrics.get("sma50"), "sma200": rec.metrics.get("sma200"),
        "atr": rec.metrics.get("atr"),
        "above_sma50": bool(rec.metrics.get("sma50") and price > rec.metrics["sma50"]),
        "above_sma200": bool(rec.metrics.get("sma200") and price > rec.metrics["sma200"]),
        "golden_cross": bool(rec.metrics.get("sma50") and rec.metrics.get("sma200")
                             and rec.metrics["sma50"] > rec.metrics["sma200"]),
        "near_52w_high": bool(last.get("High52") == last.get("High") or
                              (last.get("High52") and price >= 0.95 * last["High52"])),
        "near_52w_low": bool(last.get("Low52") and price <= 1.05 * last["Low52"]),
        "reasons": rec.reasons,
    }
    V.log_prediction(sd.symbol, rec.action, price, rec.target, rec.stop_loss)
    return row


# --------------------------------------------------------------------------- #
def cmd_recommend(args):
    for sym in args.symbols:
        with console.status(f"Analysing {sym}..."):
            sd = data.fetch_history(sym, period="1y")
            if not sd.ok:
                console.print(f"[red]{sym}: {sd.error}[/red]")
                continue
            info = data.fetch_info(sym)
            rec = analyze(sd.symbol, sd.history, info)
            V.log_prediction(sd.symbol, rec.action, rec.price, rec.target, rec.stop_loss)

        color = {"BUY": "green", "SELL": "red", "HOLD": "yellow"}[rec.action]
        header = (f"[bold]{sd.symbol}[/bold] — {rec.metrics.get('name') or ''} "
                  f"({rec.metrics.get('sector') or 'n/a'})")
        lines = [
            f"[bold {color}]Action: {rec.action}[/bold {color}]   Score: {rec.score:+.0f}   "
            f"LTP: Rs.{rec.price}",
        ]
        if rec.action in ("BUY", "SELL"):
            lines.append(
                f"Entry: Rs.{rec.entry}   Target: Rs.{rec.target}   "
                f"Stop-loss: Rs.{rec.stop_loss}   R:R {rec.risk_reward}")

        m = rec.metrics
        lines.append(
            f"RSI {m.get('rsi')} | SMA50 {m.get('sma50')} | SMA200 {m.get('sma200')} | "
            f"PE {m.get('pe')} | PEG {m.get('peg')} | ROE "
            f"{(str(round(m['roe']*100,1))+'%') if m.get('roe') is not None else 'n/a'}")
        lines.append("\n[bold]Why:[/bold]")
        lines += [f"  • {r}" for r in rec.reasons] or ["  • mixed/no strong signals"]
        console.print(Panel("\n".join(lines), title=header, border_style=color, box=ASCII_BOX))

    console.print(DISCLAIMER)


def cmd_scan(args):
    symbols = args.symbols or NIFTY50
    predicate = None
    label = "no filter"
    if args.filter:
        if args.filter not in F.PREDEFINED:
            console.print(f"[red]Unknown filter '{args.filter}'. Run `filters` to list.[/red]")
            sys.exit(1)
        predicate = F.get_predefined(args.filter)
        label = f"pre-defined: {args.filter}"
    elif args.where:
        try:
            predicate = F.compile_custom(args.where)
        except Exception as e:
            console.print(f"[red]Bad expression: {e}[/red]")
            sys.exit(1)
        label = f"custom: {args.where}"

    console.print(f"[bold]Scanning {len(symbols)} symbols[/bold] ({label})")
    rows = []
    with console.status("Fetching & analysing...") as status:
        for i, sym in enumerate(symbols, 1):
            status.update(f"[{i}/{len(symbols)}] {sym}")
            try:
                row = _scan_row(sym)
            except Exception as e:
                row = {"symbol": sym.upper(), "error": str(e)}
            rows.append(row)

    ok = [r for r in rows if not r.get("error")]
    errs = [r for r in rows if r.get("error")]
    if predicate:
        ok = [r for r in ok if predicate(r)]
    ok.sort(key=lambda r: r.get("score") or 0, reverse=True)
    if args.top:
        ok = ok[: args.top]

    table = Table(box=ASCII_BOX, header_style="bold cyan")

    for col in ["Symbol", "Action", "Score", "Price", "Target", "Stop", "R:R", "RSI", "PE", "ROE"]:
        table.add_column(col, justify="right" if col not in ("Symbol", "Action") else "left")
    for r in ok:
        a = r["action"]
        a_styled = {"BUY": f"[green]{a}[/green]", "SELL": f"[red]{a}[/red]",
                    "HOLD": f"[yellow]{a}[/yellow]"}[a]
        table.add_row(
            r["symbol"].replace(".NS", ""), a_styled, f"{r['score']:+.0f}",
            f"{r['price']:.1f}" if r.get("price") else "-",
            f"{r['target']:.1f}" if r.get("target") else "-",
            f"{r['stop_loss']:.1f}" if r.get("stop_loss") else "-",
            f"{r['rr']}" if r.get("rr") else "-",
            f"{r['rsi']}" if r.get("rsi") is not None else "-",
            f"{r['pe']:.1f}" if isinstance(r.get("pe"), (int, float)) else "-",
            f"{r['roe']*100:.0f}%" if isinstance(r.get("roe"), (int, float)) else "-",
        )
    console.print(table)
    console.print(f"[dim]{len(ok)} matched, {len(errs)} failed to fetch.[/dim]")
    if errs:
        console.print("[dim]Failed: " + ", ".join(e["symbol"] for e in errs) + "[/dim]")
    console.print(DISCLAIMER)


def cmd_filters(_args):
    table = Table(title="Pre-defined filters", box=ASCII_BOX)

    table.add_column("Name", style="bold")
    table.add_column("What it screens for")
    for name, desc in F.list_predefined():
        table.add_row(name, desc)
    console.print(table)
    console.print("\nCustom filter example: [cyan]scan --where \"rsi < 35 and roe > 0.15\"[/cyan]")
    console.print("Fields: score, price, rsi, pe, peg, roe, debt_to_equity, sma50, sma200, "
                  "above_sma50, above_sma200, golden_cross, near_52w_high, near_52w_low")


def cmd_learn(_args):
    console.print("[bold]Learning from knowledge/ (pdf/md/txt)...[/bold]")
    res = knowledge.learn()
    console.print(f"Ingested: {res['ingested'] or 'none new'}")
    console.print(f"Skipped (already learned): {res['skipped'] or 'none'}")
    console.print(f"Rules added to knowledge_graph/market_knowledge.md: {res['rules_added']}")


def cmd_verify(_args):
    def price_of(symbol: str):
        sd = data.fetch_history(symbol, period="5d")
        if sd.ok:
            return float(sd.history["Close"].iloc[-1])
        return None
    console.print("[bold]Verifying due predictions against current prices...[/bold]")
    res = V.verify(price_of)
    console.print(f"Newly evaluated: {res['evaluated_now']} | Total evaluated: {res['total_evaluated']}")
    if res["overall_hit_rate"] is not None:
        console.print(f"[bold]Overall hit-rate: {res['overall_hit_rate']}%[/bold]")
        for a, s in res["by_action"].items():
            if s["n"]:
                console.print(f"  {a}: {s['hit_rate']}% over {s['n']} calls")
    else:
        console.print("No matured predictions yet — they are evaluated 30 days after each call.")
    console.print("[dim]Log: data/predictions.csv[/dim]")


# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="stockScreener",
                                description="Indian market stock screener & recommender")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("recommend", help="Buy/Sell/Hold recommendation with reasons")
    r.add_argument("symbols", nargs="+")
    r.set_defaults(fn=cmd_recommend)

    s = sub.add_parser("scan", help="Screen a universe of stocks")
    s.add_argument("--filter", help="name of a pre-defined filter (see `filters`)")
    s.add_argument("--where", help="custom expression, e.g. 'rsi < 30 and roe > 0.15'")
    s.add_argument("--symbols", nargs="*", help="override universe (default Nifty 50)")
    s.add_argument("--top", type=int, help="keep top N by score")
    s.set_defaults(fn=cmd_scan)

    f = sub.add_parser("filters", help="list pre-defined filters")
    f.set_defaults(fn=cmd_filters)

    l = sub.add_parser("learn", help="ingest PDFs/notes from knowledge/")
    l.set_defaults(fn=cmd_learn)

    v = sub.add_parser("verify", help="score past predictions")
    v.set_defaults(fn=cmd_verify)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
