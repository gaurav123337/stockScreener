"""FastAPI backend serving the SPA (PWA) and JSON APIs.

Run:  python api.py     (or: uvicorn api:app --host 0.0.0.0 --port 8000)
Open: http://localhost:8000
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from screener.bootstrap import bootstrap, get_service
from screener.core.config import config
from screener.core.interfaces import MarketDataProvider
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

ROOT = Path(__file__).resolve().parent
LEGACY_WEB = ROOT / "web"
DIST = ROOT / "frontend" / "dist"
# Prefer the React build when present; fall back to the legacy vanilla SPA.
WEB = DIST if (DIST / "index.html").exists() else LEGACY_WEB

app = FastAPI(title="stockScreener", version="0.3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


# --------------------------------------------------------------------------- #
# Request models
# --------------------------------------------------------------------------- #
class ScanBody(BaseModel):
    symbols: list[str] | None = None
    filter: str | None = None
    where: str | None = None
    top: int | None = None


class UrlBody(BaseModel):
    url: str


class BrokerBody(BaseModel):
    broker: str
    credentials: dict


class SettingsBody(BaseModel):
    # Partial patch, e.g. {"scoring": {"buy_threshold": 40}, "risk": {...}}
    patch: dict


# --------------------------------------------------------------------------- #
# Analysis APIs
# --------------------------------------------------------------------------- #
@app.get("/api/recommend/{symbol}")
def recommend(symbol: str):
    analysis = get_service(AnalysisService)
    broker = get_service(BrokerService)
    verification = get_service(VerificationService)

    rec = analysis.analyze(symbol)
    # Use broker LTP if available
    live = broker.get_ltp(symbol)
    if live and rec.error is None:
        rec.price = round(live, 2)

    if rec.error is None:
        verification.log_prediction(rec)

    return rec.to_scan_row()


@app.post("/api/scan")
def scan(body: ScanBody):
    scan_service = get_service(ScanService)
    filter_service = get_service(FilterService)

    predicate = None
    if body.filter:
        filter_strategy = filter_service.get_filter(body.filter)
        if not filter_strategy:
            return JSONResponse({"error": f"unknown filter {body.filter}"}, 400)
        predicate = filter_strategy.matches
    elif body.where:
        try:
            expr_filter = filter_service.compile_custom(body.where)
            predicate = expr_filter.matches
        except Exception as e:
            return JSONResponse({"error": f"bad expression: {e}"}, 400)

    result = scan_service.scan(body.symbols, predicate, body.top)
    return {
        "count": len(result.matched),
        "failed": result.failed,
        "results": [r.to_scan_row() for r in result.matched],
    }


@app.get("/api/filters")
def list_filters():
    filter_service = get_service(FilterService)
    return {
        "predefined": filter_service.list_filters(),
        "fields": filter_service.get_filter_fields(),
    }


@app.get("/api/search")
def search(q: str = ""):
    """Search for a stock by symbol or company name (NSE & BSE)."""
    data = get_service(MarketDataProvider)
    searcher = getattr(data, "search", None)
    if not callable(searcher):
        return {"query": q, "results": []}
    return {"query": q, "results": searcher(q)}


@app.get("/api/verify")
def verify():
    verification = get_service(VerificationService)
    broker = get_service(BrokerService)

    def price_of(sym: str):
        live = broker.get_ltp(sym)
        if live:
            return live
        return verification.get_current_price(sym)

    return verification.verify(price_of).model_dump()


# --------------------------------------------------------------------------- #
# Settings / Dashboard APIs
# --------------------------------------------------------------------------- #
@app.get("/api/settings")
def get_settings():
    """Current value of every dashboard-editable setting."""
    return config.editable_snapshot()


@app.get("/api/settings/defaults")
def get_settings_defaults():
    """Factory defaults (for the UI 'reset to default' reference)."""
    return config._defaults()


@app.post("/api/settings")
def update_settings(body: SettingsBody):
    """Apply a partial settings patch and persist it."""
    try:
        return config.update_settings(body.patch)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.post("/api/settings/reset")
def reset_settings():
    """Restore factory defaults and clear persisted overrides."""
    return config.reset_settings()


# --------------------------------------------------------------------------- #
# Knowledge / Training APIs
# --------------------------------------------------------------------------- #
@app.post("/api/learn/file")
async def learn_file(file: UploadFile = File(...)):
    knowledge = get_service(KnowledgeService)
    content = await file.read()
    # Save to temp file then ingest
    temp_path = config.knowledge_dir / file.filename
    temp_path.write_bytes(content)
    return knowledge.learn_from_file(temp_path).model_dump()


@app.post("/api/learn/url")
def learn_url(body: UrlBody):
    knowledge = get_service(KnowledgeService)
    return knowledge.learn_from_url(body.url).model_dump()


@app.post("/api/learn")
def learn_now():
    knowledge = get_service(KnowledgeService)
    return knowledge.learn_from_directory().model_dump()


@app.get("/api/knowledge")
def get_knowledge():
    knowledge = get_service(KnowledgeService)
    return {
        "path": str(config.kb_file),
        "content": knowledge.get_knowledge_content(),
    }


# --------------------------------------------------------------------------- #
# Broker APIs
# --------------------------------------------------------------------------- #
@app.get("/api/brokers/instructions")
def broker_instructions():
    broker = get_service(BrokerService)
    return broker.get_instructions()


@app.get("/api/brokers/status")
def broker_status():
    broker = get_service(BrokerService)
    return broker.get_status()


@app.post("/api/brokers/connect")
def broker_connect(body: BrokerBody):
    broker = get_service(BrokerService)
    return broker.connect(body.broker, body.credentials)


@app.post("/api/brokers/disconnect/{broker}")
def broker_disconnect(broker: str):
    service = get_service(BrokerService)
    return service.disconnect(broker)


@app.get("/api/brokers/holdings")
def broker_holdings():
    broker = get_service(BrokerService)
    return broker.get_holdings()


# --------------------------------------------------------------------------- #
# SPA + static + PWA assets
# --------------------------------------------------------------------------- #
@app.get("/manifest.json")
def manifest():
    # Vite PWA emits manifest.webmanifest; the legacy SPA used manifest.json.
    candidate = WEB / "manifest.webmanifest"
    if not candidate.exists():
        candidate = WEB / "manifest.json"
    return FileResponse(candidate)


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


# Legacy vanilla SPA keeps its assets under web/static; the Vite build emits
# hashed assets under dist/assets (served by the catch-all above).
if LEGACY_WEB.exists() and not (DIST / "index.html").exists():
    app.mount("/static", StaticFiles(directory=LEGACY_WEB / "static"), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
