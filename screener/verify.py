"""Self-verification of predictions.

Every `analyze` call can log its recommendation to data/predictions.csv with an
evaluation horizon (default 30 trading days). `verify` looks for predictions
whose horizon has elapsed, re-fetches the current price, and scores whether the
call was directionally correct / hit target / hit stop. It reports hit-rate
overall and by action so the system can judge its own reliability.
"""
from __future__ import annotations

import csv
from datetime import datetime, date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
PRED_FILE = DATA_DIR / "predictions.csv"
FIELDS = ["ts", "symbol", "action", "price_at_call", "target", "stop_loss",
          "horizon_days", "evaluated", "eval_date", "price_at_eval",
          "outcome", "return_pct"]


def _ensure() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    if not PRED_FILE.exists():
        with PRED_FILE.open("w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writeheader()


def log_prediction(symbol: str, action: str, price: float,
                   target, stop_loss, horizon_days: int = 30) -> None:
    if action not in ("BUY", "SELL") or price is None:
        return  # only verifiable directional calls
    _ensure()
    with PRED_FILE.open("a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=FIELDS).writerow({
            "ts": datetime.now().isoformat(timespec="seconds"),
            "symbol": symbol, "action": action,
            "price_at_call": price, "target": target or "",
            "stop_loss": stop_loss or "", "horizon_days": horizon_days,
            "evaluated": "0", "eval_date": "", "price_at_eval": "",
            "outcome": "", "return_pct": "",
        })


def _due(rows: list[dict]) -> list[dict]:
    today = date.today()
    out = []
    for r in rows:
        if r["evaluated"] == "1":
            continue
        try:
            d = datetime.fromisoformat(r["ts"]).date()
        except Exception:
            continue
        if (today - d).days >= int(r["horizon_days"] or 30):
            out.append(r)
    return out


def _outcome(action: str, p0: float, p1: float, target, stop) -> tuple[str, float]:
    ret = (p1 - p0) / p0 * 100 if action == "BUY" else (p0 - p1) / p0 * 100
    if action == "BUY":
        if target and p1 >= float(target):
            return "target_hit", ret
        if stop and p1 <= float(stop):
            return "stop_hit", ret
    else:
        if target and p1 <= float(target):
            return "target_hit", ret
        if stop and p1 >= float(stop):
            return "stop_hit", ret
    return ("correct" if ret > 0 else "wrong"), ret


def verify(fetch_price) -> dict:
    """fetch_price: callable(symbol)->float|None. Returns summary stats."""
    _ensure()
    with PRED_FILE.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    due = _due(rows)
    for r in due:
        price = fetch_price(r["symbol"])
        if price is None:
            continue
        outcome, ret = _outcome(r["action"], float(r["price_at_call"]), price,
                                r["target"] or None, r["stop_loss"] or None)
        r.update({"evaluated": "1", "eval_date": date.today().isoformat(),
                  "price_at_eval": f"{price:.2f}", "outcome": outcome,
                  "return_pct": f"{ret:.2f}"})
    with PRED_FILE.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader(); w.writerows(rows)

    done = [r for r in rows if r["evaluated"] == "1"]
    wins = [r for r in done if r["outcome"] in ("target_hit", "correct")]
    by_action = {}
    for a in ("BUY", "SELL"):
        sub = [r for r in done if r["action"] == a]
        w = [r for r in sub if r["outcome"] in ("target_hit", "correct")]
        by_action[a] = {"n": len(sub), "hit_rate": round(len(w) / len(sub) * 100, 1) if sub else None}
    return {"evaluated_now": len(due), "total_evaluated": len(done),
            "overall_hit_rate": round(len(wins) / len(done) * 100, 1) if done else None,
            "by_action": by_action}
