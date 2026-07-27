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

from screener.bootstrap import bootstrap, get_service
from screener.core.config import config
from screener.services import (
    AnalysisService,
    BrokerService,
    FilterService,
    KnowledgeService,
    ScanService,
    VerificationService,
)

# Wire all dependencies
bootstrap()

# ASCII-only output so panels/tables render cleanly on legacy Windows consoles
console = Console(safe_box=True)
ASCII_BOX = box.ASCII
DISCLAIMER = "[dim]Educational tool - not SEBI-registered investment advice. Do your own research.[/dim]"


# --------------------------------------------------------------------------- #
def cmd_recommend(args):
    analysis = get_service(AnalysisService)
    verification = get_service(VerificationService)

    for sym in args.symbols:
        with console.status(f"Analysing {sym}..."):
            rec = analysis.analyze(sym)

        if rec.error:
            console.print(f"[red]{sym}: {rec.error}[/red]")
            continue

        verification.log_prediction(rec)

        color = {"BUY": "green", "SELL": "red", "HOLD": "yellow"}[rec.action.value]
        header = (f"[bold]{rec.symbol}[/bold] — {rec.metrics.name or ''} "
                  f"({rec.metrics.sector or 'n/a'})")
        lines = [
            f"[bold {color}]Action: {rec.action.value}[/bold {color}]   Score: {rec.score:+.0f}   "
            f"LTP: Rs.{rec.price}",
        ]
        if rec.action.value in ("BUY", "SELL"):
            lines.append(
                f"Entry: Rs.{rec.entry}   Target: Rs.{rec.target}   "
                f"Stop-loss: Rs.{rec.stop_loss}   R:R {rec.risk_reward}")

        m = rec.metrics
        lines.append(
            f"RSI {m.rsi} | SMA50 {m.sma50} | SMA200 {m.sma200} | "
            f"PE {m.pe} | PEG {m.peg} | ROE "
            f"{(str(round(m.roe*100,1))+'%') if m.roe is not None else 'n/a'}")
        lines.append("\n[bold]Why:[/bold]")
        lines += [f"  • {r}" for r in rec.reasons] or ["  • mixed/no strong signals"]
        console.print(Panel("\n".join(lines), title=header, border_style=color, box=ASCII_BOX))

    console.print(DISCLAIMER)


def cmd_scan(args):
    scan_service = get_service(ScanService)
    filter_service = get_service(FilterService)

    predicate = None
    label = "no filter"
    if args.filter:
        filter_strategy = filter_service.get_filter(args.filter)
        if not filter_strategy:
            console.print(f"[red]Unknown filter '{args.filter}'. Run `filters` to list.[/red]")
            sys.exit(1)
        predicate = filter_strategy.matches
        label = f"pre-defined: {args.filter}"
    elif args.where:
        try:
            expr_filter = filter_service.compile_custom(args.where)
            predicate = expr_filter.matches
        except Exception as e:
            console.print(f"[red]Bad expression: {e}[/red]")
            sys.exit(1)
        label = f"custom: {args.where}"

    symbols = args.symbols or None
    console.print(f"[bold]Scanning {len(symbols) if symbols else 50} symbols[/bold] ({label})")

    with console.status("Fetching & analysing..."):
        result = scan_service.scan(symbols, predicate, args.top)

    rows = [r.to_scan_row() for r in result.matched]
    errs = result.failed

    table = Table(box=ASCII_BOX, header_style="bold cyan")
    for col in ["Symbol", "Action", "Score", "Price", "Target", "Stop", "R:R", "RSI", "PE", "ROE"]:
        table.add_column(col, justify="right" if col not in ("Symbol", "Action") else "left")
    for r in rows:
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
    console.print(f"[dim]{len(rows)} matched, {len(errs)} failed to fetch.[/dim]")
    if errs:
        console.print("[dim]Failed: " + ", ".join(e["symbol"] for e in errs) + "[/dim]")
    console.print(DISCLAIMER)


def cmd_filters(_args):
    filter_service = get_service(FilterService)
    table = Table(title="Pre-defined filters", box=ASCII_BOX)
    table.add_column("Name", style="bold")
    table.add_column("What it screens for")
    for f in filter_service.list_filters():
        table.add_row(f["name"], f["description"])
    console.print(table)
    console.print("\nCustom filter example: [cyan]scan --where \"rsi < 35 and roe > 0.15\"[/cyan]")
    console.print("Fields: score, price, rsi, pe, peg, roe, debt_to_equity, sma50, sma200, "
                  "above_sma50, above_sma200, golden_cross, near_52w_high, near_52w_low")


def cmd_learn(_args):
    knowledge = get_service(KnowledgeService)
    console.print("[bold]Learning from knowledge/ (pdf/md/txt)...[/bold]")
    res = knowledge.learn_from_directory()
    console.print(f"Ingested: {res.ingested or 'none new'}")
    console.print(f"Skipped (already learned): {res.skipped or 'none'}")
    console.print(f"Rules added to knowledge_graph/market_knowledge.md: {res.rules_added}")


def cmd_verify(_args):
    verification = get_service(VerificationService)
    broker = get_service(BrokerService)

    def price_of(symbol: str):
        live = broker.get_ltp(symbol)
        if live:
            return live
        from screener.infrastructure.data.yahoo_provider import YahooDataProvider
        provider = YahooDataProvider()
        df = provider.fetch_history(symbol, period="5d")
        return float(df["Close"].iloc[-1]) if df is not None and not df.empty else None

    console.print("[bold]Verifying due predictions against current prices...[/bold]")
    res = verification.verify(price_of)
    console.print(f"Newly evaluated: {res.evaluated_now} | Total evaluated: {res.total_evaluated}")
    if res.overall_hit_rate is not None:
        console.print(f"[bold]Overall hit-rate: {res.overall_hit_rate}%[/bold]")
        for a, s in res.by_action.items():
            if s["n"]:
                console.print(f"  {a}: {s['hit_rate']}% over {s['n']} calls")
    else:
        console.print("No matured predictions yet — they are evaluated 30 days after each call.")
    console.print(f"[dim]Log: {config.predictions_file}[/dim]")


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
