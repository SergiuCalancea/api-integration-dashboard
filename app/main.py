"""FastAPI application: REST endpoints + static frontend.

Run with:  uvicorn app.main:app --reload
"""

import asyncio
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .cache import TTLCache
from .config import settings
from .services import crypto, currency, telegram, weather
from .services.http import NotFoundError, UpstreamError

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
COIN_RE = re.compile(r"^[a-z0-9-]{2,40}$")
DEFAULT_SYMBOLS = "USD,GBP,RON,CHF,JPY"
DEFAULT_COINS = "bitcoin,ethereum,solana,cardano"

cache = TTLCache(settings.cache_ttl_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # One shared connection pool for all outgoing requests.
    async with httpx.AsyncClient(
        timeout=settings.request_timeout,
        headers={"User-Agent": "GlobalPulse/1.0 (portfolio demo)"},
    ) as client:
        app.state.http = client
        yield


app = FastAPI(
    title="Global Pulse API",
    description="Aggregates weather, exchange rates and crypto prices from public APIs "
    "and pushes digests to Telegram.",
    version="1.0.0",
    lifespan=lifespan,
)


def get_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http


Client = Annotated[httpx.AsyncClient, Depends(get_client)]


@app.exception_handler(UpstreamError)
async def upstream_error_handler(_: Request, exc: UpstreamError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message, "service": exc.service})


@app.exception_handler(NotFoundError)
async def not_found_handler(_: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": exc.message})


def parse_list(raw: str, pattern: re.Pattern[str], upper: bool = False) -> list[str]:
    items = [i.strip().upper() if upper else i.strip().lower() for i in raw.split(",") if i.strip()]
    items = list(dict.fromkeys(items))  # de-duplicate, keep order
    if not items or len(items) > 10 or not all(pattern.match(i) for i in items):
        raise HTTPException(422, f"Invalid list: '{raw}'")
    return items


# ---------------------------------------------------------------- endpoints


@app.get("/api/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "telegram_enabled": settings.telegram_enabled, "default_city": settings.default_city}


@app.get("/api/weather", tags=["weather"])
async def get_weather(
    client: Client, city: Annotated[str, Query(min_length=2, max_length=80)] = settings.default_city
) -> dict:
    city = city.strip()
    return await cache.get_or_set(f"weather:{city.lower()}", lambda: weather.get_weather(client, city))


@app.get("/api/currencies", tags=["currency"])
async def get_currencies(client: Client) -> dict[str, str]:
    return await cache.get_or_set("currencies", lambda: currency.get_currencies(client))


@app.get("/api/rates", tags=["currency"])
async def get_rates(
    client: Client,
    base: Annotated[str, Query(pattern=r"^[A-Za-z]{3}$")] = "EUR",
    symbols: str = DEFAULT_SYMBOLS,
    days: Annotated[int, Query(ge=7, le=365)] = 30,
) -> dict:
    base = base.upper()
    symbol_list = parse_list(symbols, CURRENCY_RE, upper=True)
    key = f"rates:{base}:{','.join(symbol_list)}:{days}"
    return await cache.get_or_set(key, lambda: currency.get_rates(client, base, symbol_list, days))


@app.get("/api/crypto", tags=["crypto"])
async def get_crypto(
    client: Client,
    ids: str = DEFAULT_COINS,
    vs: Annotated[str, Query(pattern=r"^[a-z]{3}$")] = "usd",
) -> list[dict]:
    coin_ids = parse_list(ids, COIN_RE)
    return await cache.get_or_set(f"crypto:{','.join(coin_ids)}:{vs}", lambda: crypto.get_prices(client, coin_ids, vs))


@app.get("/api/crypto/{coin_id}/history", tags=["crypto"])
async def get_crypto_history(
    client: Client,
    coin_id: str,
    days: Annotated[int, Query(ge=1, le=90)] = 7,
    vs: Annotated[str, Query(pattern=r"^[a-z]{3}$")] = "usd",
) -> dict:
    if not COIN_RE.match(coin_id):
        raise HTTPException(422, "Invalid coin id")
    return await cache.get_or_set(
        f"crypto-history:{coin_id}:{vs}:{days}", lambda: crypto.get_history(client, coin_id, vs, days)
    )


class NotifyRequest(BaseModel):
    city: str = Field(default=settings.default_city, min_length=2, max_length=80)
    base: str = Field(default="EUR", pattern=r"^[A-Za-z]{3}$")


@app.post("/api/notify", tags=["telegram"])
async def notify(client: Client, body: NotifyRequest) -> dict:
    """Collect data from every integration and push a digest to Telegram."""
    if not settings.telegram_enabled:
        raise HTTPException(503, "Telegram is not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
    weather_data, rates_data, crypto_data = await asyncio.gather(
        get_weather(client, body.city),
        get_rates(client, body.base, DEFAULT_SYMBOLS, 30),
        get_crypto(client, DEFAULT_COINS, "usd"),
    )
    text = telegram.build_digest(weather_data, rates_data, crypto_data)
    await telegram.send_message(client, settings.telegram_bot_token, settings.telegram_chat_id, text)
    return {"sent": True, "preview": text}


# Frontend (mounted last so /api/* routes take priority).
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
