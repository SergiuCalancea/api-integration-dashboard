"""Exchange-rate integration using the Frankfurter API (ECB data, no API key)."""

from datetime import date, timedelta
from typing import Any

import httpx

from .http import get_json

BASE_URL = "https://api.frankfurter.dev/v1"
SERVICE = "Frankfurter"


async def get_currencies(client: httpx.AsyncClient) -> dict[str, str]:
    """Return the supported currencies as {"USD": "United States Dollar", ...}."""
    return await get_json(client, f"{BASE_URL}/currencies", None, SERVICE)


async def get_rates(
    client: httpx.AsyncClient, base: str, symbols: list[str], days: int
) -> dict[str, Any]:
    """Latest rates plus a daily time series for the last `days` days."""
    symbols = [s for s in symbols if s != base]
    params = {"base": base, "symbols": ",".join(symbols)}

    latest = await get_json(client, f"{BASE_URL}/latest", params, SERVICE)
    start = date.today() - timedelta(days=days)
    history = await get_json(client, f"{BASE_URL}/{start.isoformat()}..", params, SERVICE)

    dates = sorted(history.get("rates", {}))
    series: dict[str, list[float | None]] = {s: [] for s in symbols}
    for day in dates:
        for symbol in symbols:
            series[symbol].append(history["rates"][day].get(symbol))

    changes: dict[str, float | None] = {}
    for symbol, values in series.items():
        clean = [v for v in values if v is not None]
        changes[symbol] = round((clean[-1] - clean[0]) / clean[0] * 100, 3) if len(clean) > 1 else None

    return {
        "base": latest["base"],
        "date": latest["date"],
        "rates": latest["rates"],
        "change_pct": changes,
        "history": {"dates": dates, "series": series},
    }
