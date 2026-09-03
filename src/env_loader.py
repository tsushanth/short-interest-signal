"""Loads Alpaca paper-trading credentials from the NewsTrader project's
.env file (this project's own credential source -- these keys are already
in use elsewhere in the portfolio, no new account setup needed).

Deliberately never prints the key values anywhere -- only confirms
presence/absence.
"""
import os
from pathlib import Path

NEWSTRADER_ENV = Path.home() / "Documents/GitHub/NewsTrader/.env"


def load_alpaca_credentials() -> tuple[str, str]:
    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")
    if api_key and secret_key:
        return api_key, secret_key

    if not NEWSTRADER_ENV.exists():
        raise RuntimeError(f"no ALPACA_API_KEY/SECRET_KEY in env and {NEWSTRADER_ENV} not found")

    values = {}
    for line in NEWSTRADER_ENV.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        values[k.strip()] = v.strip().strip('"').strip("'")

    api_key = values.get("ALPACA_API_KEY")
    secret_key = values.get("ALPACA_SECRET_KEY")
    if not api_key or not secret_key:
        raise RuntimeError(f"ALPACA_API_KEY/ALPACA_SECRET_KEY not found in {NEWSTRADER_ENV}")
    return api_key, secret_key
