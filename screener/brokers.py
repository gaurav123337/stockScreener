"""Optional broker API integration (Zerodha Kite & Angel One SmartAPI).

These are OPTIONAL adapters. If you connect one, the app can pull live quotes,
your holdings and positions for richer results. If a broker library or
credentials are missing, every function degrades gracefully and the app keeps
working on free Yahoo data.

Settings are stored in data/broker_settings.json (never commit real tokens).

Setup instructions are exposed via GET /api/brokers/instructions.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SETTINGS = DATA_DIR / "broker_settings.json"

# --------------------------------------------------------------------------- #
INSTRUCTIONS = {
    "zerodha": {
        "name": "Zerodha Kite Connect",
        "library": "pip install kiteconnect",
        "steps": [
            "1. Open a Zerodha account, then visit https://kite.trade and create a Kite Connect app.",
            "2. Note your API Key and API Secret.",
            "3. Kite Connect uses a daily login: you must generate a 'request_token' via the login URL.",
            "4. Exchange the request_token for an access_token (valid ~1 day) using your secret.",
            "5. Paste api_key + access_token below and Save. Quote/holdings will use Kite.",
            "Note: tokens expire daily; re-login each morning (this is a Zerodha rule).",
        ],
        "fields": ["api_key", "access_token"],
    },
    "angelone": {
        "name": "Angel One SmartAPI",
        "library": "pip install smartapi-python",
        "steps": [
            "1. Open an Angel One account and register at https://smartapi.angelone.in to get an API key.",
            "2. Enable TOTP in your Angel One app and note your client code, PIN (mpin) and TOTP secret.",
            "3. SmartAPI requires a session generated with clientcode + pin + totp.",
            "4. Paste api_key, client_code, pin and totp_secret below and Save.",
            "5. We create the session on demand; the feed token is fetched automatically.",
        ],
        "fields": ["api_key", "client_code", "pin", "totp_secret"],
    },
}


def _load() -> dict:
    if SETTINGS.exists():
        try:
            return json.loads(SETTINGS.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def get_settings() -> dict:
    """Return settings with secrets masked for display."""
    raw = _load()
    masked = {}
    for broker, conf in raw.items():
        masked[broker] = {k: ("****" + str(v)[-3:] if v else "") for k, v in conf.items()}
        masked[broker]["connected"] = bool(raw.get(broker, {}).get("connected"))
    return masked


def save_settings(broker: str, conf: dict) -> dict:
    DATA_DIR.mkdir(exist_ok=True)
    raw = _load()
    raw.setdefault(broker, {})
    for k, v in conf.items():
        if v and not str(v).startswith("****"):
            raw[broker][k] = v
    raw[broker]["connected"] = True
    SETTINGS.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    return {"ok": True, "broker": broker}


def disconnect(broker: str) -> dict:
    raw = _load()
    if broker in raw:
        raw[broker]["connected"] = False
        SETTINGS.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    return {"ok": True}


def status() -> dict:
    raw = _load()
    out = {}
    for b in ("zerodha", "angelone"):
        conf = raw.get(b, {})
        lib_ok, lib_name = _lib_available(b)
        out[b] = {
            "connected": bool(conf.get("connected")),
            "library_installed": lib_ok,
            "library": lib_name,
            "credentials_present": bool(any(conf.get(k) for k in ("api_key", "access_token", "client_code"))),
        }
    return out


def _lib_available(broker: str):
    try:
        if broker == "zerodha":
            import kiteconnect  # noqa
            return True, "kiteconnect"
        if broker == "angelone":
            import SmartApi  # noqa
            return True, "smartapi-python"
    except Exception:
        return False, "kiteconnect" if broker == "zerodha" else "smartapi-python"
    return False, ""


# --------------------------------------------------------------------------- #
def _zerodha_client():
    conf = _load().get("zerodha", {})
    if not conf.get("connected"):
        return None
    try:
        from kiteconnect import KiteConnect
        kite = KiteConnect(api_key=conf.get("api_key"))
        kite.set_access_token(conf.get("access_token"))
        return kite
    except Exception:
        return None


def _angel_client():
    conf = _load().get("angelone", {})
    if not conf.get("connected"):
        return None
    try:
        from SmartApi import SmartConnect
        import pyotp
        obj = SmartConnect(api_key=conf.get("api_key"))
        totp = pyotp.TOTP(conf.get("totp_secret")).now()
        sess = obj.generateSession(conf.get("client_code"), conf.get("pin"), totp)
        if sess.get("status"):
            return obj
    except Exception:
        return None
    return None


def get_ltp(symbol: str) -> float | None:
    """Try connected brokers for a live LTP, else None (caller falls back to Yahoo)."""
    sym = symbol.upper().replace(".NS", "").replace(".BO", "")
    kite = _zerodha_client()
    if kite:
        try:
            q = kite.ltp([f"NSE:{sym}"])
            return float(q[f"NSE:{sym}"]["last_price"])
        except Exception:
            pass
    angel = _angel_client()
    if angel:
        try:
            # Angel needs an instrument token; without the master contract we skip.
            pass
        except Exception:
            pass
    return None


def get_holdings() -> dict:
    """Return holdings/positions from any connected broker."""
    kite = _zerodha_client()
    if kite:
        try:
            return {"broker": "zerodha", "holdings": kite.holdings(),
                    "positions": kite.positions()}
        except Exception as e:
            return {"broker": "zerodha", "error": str(e)}
    angel = _angel_client()
    if angel:
        try:
            return {"broker": "angelone", "holdings": angel.holding(),
                    "positions": angel.position()}
        except Exception as e:
            return {"broker": "angelone", "error": str(e)}
    return {"broker": None, "error": "no broker connected"}
