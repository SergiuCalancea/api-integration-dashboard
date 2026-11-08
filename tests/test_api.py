"""API tests. All external HTTP calls are mocked with httpx.MockTransport,
so the suite is fast, deterministic and runs offline."""

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.services.telegram import build_digest

GEO = {"results": [{"name": "Chisinau", "country": "Moldova", "latitude": 47.0, "longitude": 28.86}]}
FORECAST = {
    "timezone": "Europe/Chisinau",
    "current": {
        "time": "2026-11-08T14:15",
        "temperature_2m": 9.4,
        "apparent_temperature": 7.1,
        "relative_humidity_2m": 71,
        "wind_speed_10m": 12.3,
        "weather_code": 3,
        "is_day": 1,
    },
    "hourly": {
        "time": [f"2026-11-08T{h:02d}:00" for h in range(24)] + [f"2026-11-09T{h:02d}:00" for h in range(24)],
        "temperature_2m": list(range(48)),
        "precipitation_probability": [10] * 48,
    },
    "daily": {
        "time": ["2026-11-08", "2026-11-09"],
        "weather_code": [3, 61],
        "temperature_2m_max": [11.0, 8.0],
        "temperature_2m_min": [4.0, 3.0],
    },
}
LATEST = {"base": "EUR", "date": "2026-11-06", "rates": {"USD": 1.1, "RON": 4.97}}
HISTORY = {
    "base": "EUR",
    "rates": {"2026-10-09": {"USD": 1.0, "RON": 5.0}, "2026-11-06": {"USD": 1.1, "RON": 4.97}},
}
PRICES = {"bitcoin": {"usd": 70000, "usd_24h_change": 2.5, "usd_market_cap": 1.4e12}}
CHART = {"prices": [[1762560000000, 69000.0], [1762563600000, 70000.0]]}


def handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if "geocoding-api" in url:
        return httpx.Response(200, json=GEO if "Chisinau" in url else {})
    if "api.open-meteo.com" in url:
        return httpx.Response(200, json=FORECAST)
    if "frankfurter" in url:
        if url.endswith("/currencies"):
            return httpx.Response(200, json={"EUR": "Euro", "USD": "US Dollar"})
        return httpx.Response(200, json=LATEST if "/latest" in url else HISTORY)
    if "simple/price" in url:
        return httpx.Response(200, json=PRICES)
    if "market_chart" in url:
        return httpx.Response(429 if "dogecoin" in url else 200, json=CHART)
    if "api.telegram.org" in url:
        return httpx.Response(200, json={"ok": True})
    return httpx.Response(404)


@pytest.fixture
def client():
    mock = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    main.app.dependency_overrides[main.get_client] = lambda: mock
    main.cache.clear()
    with TestClient(main.app) as c:
        yield c
    main.app.dependency_overrides.clear()


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_weather_returns_next_24_hours(client):
    data = client.get("/api/weather?city=Chisinau").json()
    assert data["location"]["country"] == "Moldova"
    assert data["current"]["description"] == "Overcast"
    assert data["hourly"]["time"][0] == "2026-11-08T14:00"
    assert len(data["hourly"]["temperature"]) == 24
    assert data["daily"][1]["icon"] == "rain"


def test_unknown_city_is_404(client):
    r = client.get("/api/weather?city=Atlantis")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"]


def test_rates_compute_change(client):
    data = client.get("/api/rates?base=eur&symbols=USD,RON").json()
    assert data["rates"]["USD"] == 1.1
    assert data["change_pct"]["USD"] == pytest.approx(10.0)
    assert data["history"]["dates"] == ["2026-10-09", "2026-11-06"]


def test_rates_reject_bad_symbols(client):
    assert client.get("/api/rates?symbols=US$,XX").status_code == 422


def test_crypto_prices(client):
    coins = client.get("/api/crypto?ids=bitcoin").json()
    assert coins[0] == {"id": "bitcoin", "price": 70000, "change_24h": 2.5, "market_cap": 1.4e12, "currency": "usd"}


def test_crypto_rate_limit_is_reported(client):
    r = client.get("/api/crypto/dogecoin/history")
    assert r.status_code == 503
    assert "rate limit" in r.json()["detail"]


def test_notify_requires_configuration(client, monkeypatch):
    monkeypatch.setattr(main, "settings", main.settings.__class__(telegram_bot_token="", telegram_chat_id=""))
    assert client.post("/api/notify", json={}).status_code == 503


def test_notify_sends_digest(client, monkeypatch):
    monkeypatch.setattr(main, "settings", main.settings.__class__(telegram_bot_token="t", telegram_chat_id="1"))
    r = client.post("/api/notify", json={"city": "Chisinau"})
    assert r.status_code == 200
    assert "Chisinau" in r.json()["preview"]


def test_build_digest_escapes_html():
    weather = {
        "location": {"name": "<b>X</b>", "country": "Y"},
        "current": {"temperature": 1, "description": "Fog", "feels_like": 0, "wind_speed": 3},
    }
    text = build_digest(weather, {"base": "EUR", "rates": {}, "change_pct": {}}, [])
    assert "&lt;b&gt;X&lt;/b&gt;" in text


def test_frontend_is_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Global Pulse" in r.text
