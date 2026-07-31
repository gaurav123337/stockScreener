"""Manual live smoke check for the optional Indian market provider.

This command is intentionally excluded from pytest/CI because it consumes live
quota. It prints only status and timing metadata, never credentials or payloads.
"""
from __future__ import annotations

import argparse
import json
import sys

from screener.core.config import IndianApiConfig
from screener.infrastructure.data.indian_api_client import IndianApiClient


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test Indian API connectivity")
    parser.add_argument("--stock", help="Optional provider stock/company identifier")
    args = parser.parse_args()

    settings = IndianApiConfig()
    if not settings.enabled or not settings.base_url or not settings.api_key:
        print("Indian API smoke test requires enabled=true, base_url, and api_key.", file=sys.stderr)
        return 2

    client = IndianApiClient(settings)
    checks: list[tuple[str, object]] = [("trending", lambda: client.snapshot("trending"))]
    if args.stock:
        checks.append(("stock", lambda: client.stock(args.stock)))

    failures: list[str] = []
    for name, check in checks:
        try:
            check()
            print(f"PASS {name}")
        except Exception as exc:  # Manual diagnostic boundary.
            failures.append(name)
            print(f"FAIL {name}: {type(exc).__name__}", file=sys.stderr)

    print(json.dumps(client.telemetry().model_dump(), indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())