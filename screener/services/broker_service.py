"""Broker Service — unified broker management with plugin adapters."""
from __future__ import annotations

import json
from typing import Any

from screener.core.config import config
from screener.core.models import BrokerStatus, Holding
from screener.core.plugins import registry


class ZerodhaAdapter:
    """Zerodha Kite Connect adapter."""

    INSTRUCTIONS = {
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
    }

    def __init__(self):
        self._settings_file = config.broker_settings_file

    @property
    def name(self) -> str:
        return "zerodha"

    def _load(self) -> dict:
        if self._settings_file.exists():
            try:
                return json.loads(self._settings_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save(self, data: dict) -> None:
        self._settings_file.parent.mkdir(parents=True, exist_ok=True)
        self._settings_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def is_connected(self) -> bool:
        return bool(self._load().get("zerodha", {}).get("connected"))

    def status(self) -> BrokerStatus:
        conf = self._load().get("zerodha", {})
        lib_ok = False
        try:
            import kiteconnect  # noqa
            lib_ok = True
        except ImportError:
            pass
        return BrokerStatus(
            connected=bool(conf.get("connected")),
            library_installed=lib_ok,
            library="kiteconnect",
            credentials_present=bool(conf.get("api_key") and conf.get("access_token")),
        )

    def connect(self, credentials: dict) -> bool:
        data = self._load()
        data.setdefault("zerodha", {})
        for k, v in credentials.items():
            if v and not str(v).startswith("****"):
                data["zerodha"][k] = v
        data["zerodha"]["connected"] = True
        self._save(data)
        return True

    def disconnect(self) -> bool:
        data = self._load()
        if "zerodha" in data:
            data["zerodha"]["connected"] = False
            self._save(data)
        return True

    def _client(self):
        conf = self._load().get("zerodha", {})
        if not conf.get("connected"):
            return None
        try:
            from kiteconnect import KiteConnect
            kite = KiteConnect(api_key=conf.get("api_key"))
            kite.set_access_token(conf.get("access_token"))
            return kite
        except Exception:
            return None

    def get_ltp(self, symbol: str) -> float | None:
        kite = self._client()
        if not kite:
            return None
        sym = symbol.upper().replace(".NS", "").replace(".BO", "")
        try:
            q = kite.ltp([f"NSE:{sym}"])
            return float(q[f"NSE:{sym}"]["last_price"])
        except Exception:
            return None

    def get_holdings(self) -> list[Holding]:
        kite = self._client()
        if not kite:
            return []
        try:
            holdings = kite.holdings()
            return [
                Holding(
                    symbol=h.get("tradingsymbol", ""),
                    quantity=float(h.get("quantity", 0)),
                    average_price=float(h.get("average_price", 0)),
                    current_price=float(h.get("last_price", 0)) if h.get("last_price") else None,
                    pnl=float(h.get("pnl", 0)) if h.get("pnl") else None,
                    broker="zerodha",
                    raw=h,
                )
                for h in holdings
            ]
        except Exception:
            return []


class AngelOneAdapter:
    """Angel One SmartAPI adapter."""

    INSTRUCTIONS = {
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
    }

    def __init__(self):
        self._settings_file = config.broker_settings_file

    @property
    def name(self) -> str:
        return "angelone"

    def _load(self) -> dict:
        if self._settings_file.exists():
            try:
                return json.loads(self._settings_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save(self, data: dict) -> None:
        self._settings_file.parent.mkdir(parents=True, exist_ok=True)
        self._settings_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def is_connected(self) -> bool:
        return bool(self._load().get("angelone", {}).get("connected"))

    def status(self) -> BrokerStatus:
        conf = self._load().get("angelone", {})
        lib_ok = False
        try:
            import SmartApi  # noqa
            lib_ok = True
        except ImportError:
            pass
        return BrokerStatus(
            connected=bool(conf.get("connected")),
            library_installed=lib_ok,
            library="smartapi-python",
            credentials_present=bool(conf.get("api_key") and conf.get("client_code")),
        )

    def connect(self, credentials: dict) -> bool:
        data = self._load()
        data.setdefault("angelone", {})
        for k, v in credentials.items():
            if v and not str(v).startswith("****"):
                data["angelone"][k] = v
        data["angelone"]["connected"] = True
        self._save(data)
        return True

    def disconnect(self) -> bool:
        data = self._load()
        if "angelone" in data:
            data["angelone"]["connected"] = False
            self._save(data)
        return True

    def _client(self):
        conf = self._load().get("angelone", {})
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

    def get_ltp(self, symbol: str) -> float | None:
        # Angel One requires instrument token lookup; skip for now
        return None

    def get_holdings(self) -> list[Holding]:
        angel = self._client()
        if not angel:
            return []
        try:
            holdings = angel.holding()
            return [
                Holding(
                    symbol=h.get("tradingsymbol", ""),
                    quantity=float(h.get("quantity", 0)),
                    average_price=float(h.get("averageprice", 0)),
                    current_price=float(h.get("ltp", 0)) if h.get("ltp") else None,
                    pnl=float(h.get("profitandloss", 0)) if h.get("profitandloss") else None,
                    broker="angelone",
                    raw=h,
                )
                for h in holdings
            ]
        except Exception:
            return []


class BrokerService:
    """Unified broker management."""

    def __init__(self):
        # Auto-register adapters
        registry.register_broker(ZerodhaAdapter())
        registry.register_broker(AngelOneAdapter())

    def get_instructions(self) -> dict[str, Any]:
        return {
            "zerodha": ZerodhaAdapter.INSTRUCTIONS,
            "angelone": AngelOneAdapter.INSTRUCTIONS,
        }

    def get_status(self) -> dict[str, BrokerStatus]:
        return {
            name: registry.get_broker(name).status()
            for name in registry.list_brokers()
        }

    def connect(self, broker_name: str, credentials: dict) -> dict[str, Any]:
        broker = registry.get_broker(broker_name)
        if not broker:
            return {"ok": False, "error": f"unknown broker {broker_name}"}
        success = broker.connect(credentials)
        return {"ok": success, "broker": broker_name}

    def disconnect(self, broker_name: str) -> dict[str, Any]:
        broker = registry.get_broker(broker_name)
        if not broker:
            return {"ok": False, "error": f"unknown broker {broker_name}"}
        success = broker.disconnect()
        return {"ok": success}

    def get_ltp(self, symbol: str) -> float | None:
        """Try all connected brokers for live LTP."""
        broker = registry.get_connected_broker()
        if broker:
            return broker.get_ltp(symbol)
        return None

    def get_holdings(self) -> dict[str, Any]:
        """Get holdings from first connected broker."""
        broker = registry.get_connected_broker()
        if not broker:
            return {"broker": None, "error": "no broker connected", "holdings": []}
        holdings = broker.get_holdings()
        return {
            "broker": broker.name,
            "holdings": [h.model_dump() for h in holdings],
        }
