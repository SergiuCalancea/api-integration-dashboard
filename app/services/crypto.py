"""Crypto market integration using the public CoinGecko API (no API key)."""

from typing import Any

import httpx

from .http import NotFoundError, get_json

BASE_URL = "https://api.coingecko.com/api/v3"
SERVICE = "CoinGecko"


async def get_prices(client: httpx.AsyncClient, ids: list[str], vs: str) -> list[dict[str, Any]]:
    data = await get_json(
        client,
        f"{BASE_URL}/simple/price",
        {
            "ids": ",".join(ids),
            "vs_currencies": vs,
            "include_24hr_change": "true",
            "include_market_cap": "true",
        },
        SERVICE,
    )
    return [
        {
            "id": coin,
            "price": data[coin].get(vs),
            "change_24h": data[coin].get(f"{vs}_24h_change"),
            "market_cap": data[coin].get(f"{vs}_market_cap"),
            "currency": vs,
        }
        for coin in ids
        if coin in data
    ]


async def get_history(client: httpx.AsyncClient, coin_id: str, vs: str, days: int) -> dict[str, Any]:
    data = await get_json(
        client,
        f"{BASE_URL}/coins/{coin_id}/market_chart",
        {"vs_currency": vs, "days": days},
        SERVICE,
    )
    prices = data.get("prices") or []
    if not prices:
        raise NotFoundError(f"No price history for '{coin_id}'")
    return {
        "id": coin_id,
        "currency": vs,
        "days": days,
        "timestamps": [int(p[0]) for p in prices],
        "prices": [p[1] for p in prices],
    }
