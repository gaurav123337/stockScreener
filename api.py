"""FastAPI backend serving the SPA (PWA) and JSON APIs.

Run:  python api.py     (or: uvicorn api:app --host 0.0.0.0 --port 8000)
Open: http://localhost:8000
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from screener import data, filters as F, knowledge, verify as V, brokers
from screener.indicators import add_all
from screener.signals import analyze
from screener.universe import NIFTY50

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"

app = FastAPI(title="stockScreener", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _rec_to_dict(symbol: str) -> dict:
    sd = data.fetch_history(symbol, period="1y")
    if not sd.ok:
        return {"symbol": symbol.upper(), "error": sd.error}
    info = data.fetch_info(symbol)
    rec = analyze(sd.symbol, sd.history, info)
    df = add_all(sd.history)
    last = df.iloc[-1]
    price = rec.price
    live = brokers.get_ltp(symbol)  # use broker LTP if a broker is connected
    if live:
        price = round(live, 2)
    m = rec.metrics
    row = {
        "symbol": sd.symbol, "name": m.get("name") or "", "sector": m.get("sector"),
        "action": rec.action, "score": rec.score, "price": price,
        "entry": rec.entry, "target": rec.target, "stop_loss": rec.stop_loss,
        "rr": rec.risk_reward, "reasons": rec.reasons,
        "rsi": m.get("rsi"), "pe": m.get("pe"), "peg": m.get("peg"),
        "roe": m.get("roe"), "debt_to_equity": m.get("debt_to_equity"),
        "sma50": m.get("sma50"), "sma200": m.get("sma200"), "atr": m.get("atr"),
        "above_sma50": bool(m.get("sma50") and price > m["sma50"]),
        "above_sma200": bool(m.get("sma200") and price > m["sma200"]),
        "golden_cross": bool(m.get("sma50") and m.get("sma200") and m["sma50"] > m["sma200"]),
        "near_52w_high": bool(last.get("High52") and price >= 0.95 * last["High52"]),
        "near_52w_low": bool(last.get("Low52") and price <= 1.05 * last["Low52"]),
    }
    V.log_prediction(sd.symbol, rec.action, price, rec.target, rec.stop_loss)
    return row


# --------------------------------------------------------------------------- #
# analysis APIs
# --------------------------------------------------------------------------- #
@app.get("/api/recommend/{symbol}")
def recommend(symbol: str):
    return _rec_to_dict(symbol)


class ScanBody(BaseModel):
    symbols: list[str] | None = None
    filter: str | None = None
    where: str | None = None
    top: int | None = None


@app.post("/api/scan")
def scan(body: ScanBody):
    symbols = body.symbols or NIFTY50
    predicate = None
    if body.filter:
        if body.filter not in F.PREDEFINED:
            return JSONResponse({"error": f"unknown filter {body.filter}"}, 400)
        predicate = F.get_predefined(body.filter)
    elif body.where:
        try:
            predicate = F.compile_custom(body.where)
        except Exception as e:
            return JSONResponse({"error": f"bad expression: {e}"}, 400)

    with ThreadPoolExecutor(max_workers=8) as ex:
        rows = list(ex.map(_rec_to_dict, symbols))
    ok = [r for r in rows if not r.get("error")]
    errs = [{"symbol": r["symbol"], "error": r["error"]} for r in rows if r.get("error")]
    if predicate:
        ok = [r for r in ok if predicate(r)]
    ok.sort(key=lambda r: r.get("score") or 0, reverse=True)
    if body.top:
        ok = ok[: body.top]
    return {"count": len(ok), "failed": errs, "results": ok}


@app.get("/api/filters")
def list_filters():
    return {"predefined": [{"name": n, "desc": d} for n, d in F.list_predefined()],
            "fields": ["score", "price", "rsi", "pe", "peg", "roe", "debt_to_equity",
                       "sma50", "sma200", "above_sma50", "above_sma200",
                       "golden_cross", "near_52w_high", "near_52w_low"]}


@app.get("/api/verify")
def verify():
    def price_of(sym: str):
        live = brokers.get_ltp(sym)
        if live:
            return live
        sd = data.fetch_history(sym, period="5d")
        return float(sd.history["Close"].iloc[-1]) if sd.ok else None
    return V.verify(price_of)


# --------------------------------------------------------------------------- #
# knowledge / training APIs
# --------------------------------------------------------------------------- #
@app.post("/api/learn/file")
async def learn_file(file: UploadFile = File(...)):
    content = await file.read()
    return knowledge.ingest_bytes(file.filename, content)


class UrlBody(BaseModel):
    url: str


@app.post("/api/learn/url")
def learn_url(body: UrlBody):
    return knowledge.ingest_url(body.url)


@app.post("/api/learn")
def learn_now():
    return knowledge.learn(verbose=False)


@app.get("/api/knowledge")
def get_knowledge():
    kb = knowledge.KB_FILE
    return {"path": str(kb), "content": kb.read_text(encoding="utf-8") if kb.exists() else ""}


# --------------------------------------------------------------------------- #
# broker APIs
# --------------------------------------------------------------------------- #
@app.get("/api/brokers/instructions")
def broker_instructions():
    return brokers.INSTRUCTIONS


@app.get("/api/brokers/status")
def broker_status():
    return brokers.status()


class BrokerBody(BaseModel):
    broker: str
    credentials: dict


@app.post("/api/brokers/connect")
def broker_connect(body: BrokerBody):
    if body.broker not in ("zerodha", "angelone"):
        return JSONResponse({"error": "broker must be zerodha or angelone"}, 400)
    return brokers.save_settings(body.broker, body.credentials)


@app.post("/api/brokers/disconnect/{broker}")
def broker_disconnect(broker: str):
    return brokers.disconnect(broker)


@app.get("/api/brokers/holdings")
def broker_holdings():
    return brokers.get_holdings()


# --------------------------------------------------------------------------- #
# SPA + static + PWA assets
# --------------------------------------------------------------------------- #
@app.get("/manifest.json")
def manifest():
    return FileResponse(WEB / "manifest.json")


@app.get("/sw.js")
def service_worker():
    return FileResponse(WEB / "sw.js", media_type="application/javascript")


@app.get("/{full_path:path}")
def spa(full_path: str):
    # serve real files if they exist (css/js/icons), else index.html (SPA routing)
    candidate = WEB / full_path
    if full_path and candidate.exists() and candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(WEB / "index.html")


if WEB.exists():
    app.mount("/static", StaticFiles(directory=WEB / "static"), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
