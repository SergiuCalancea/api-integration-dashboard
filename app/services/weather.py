"""Weather integration using Open-Meteo (free, no API key required).

Two calls are chained: the Geocoding API turns a city name into coordinates,
then the Forecast API returns current conditions, hourly and daily data.
"""

from typing import Any

import httpx

from .http import NotFoundError, get_json

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
SERVICE = "Open-Meteo"

# WMO weather interpretation codes -> (description, icon key used by the frontend)
WMO_CODES: dict[int, tuple[str, str]] = {
    0: ("Clear sky", "clear"),
    1: ("Mainly clear", "clear"),
    2: ("Partly cloudy", "partly"),
    3: ("Overcast", "cloudy"),
    45: ("Fog", "fog"),
    48: ("Rime fog", "fog"),
    51: ("Light drizzle", "drizzle"),
    53: ("Drizzle", "drizzle"),
    55: ("Dense drizzle", "drizzle"),
    56: ("Freezing drizzle", "drizzle"),
    57: ("Freezing drizzle", "drizzle"),
    61: ("Light rain", "rain"),
    63: ("Rain", "rain"),
    65: ("Heavy rain", "rain"),
    66: ("Freezing rain", "rain"),
    67: ("Freezing rain", "rain"),
    71: ("Light snow", "snow"),
    73: ("Snow", "snow"),
    75: ("Heavy snow", "snow"),
    77: ("Snow grains", "snow"),
    80: ("Rain showers", "rain"),
    81: ("Rain showers", "rain"),
    82: ("Violent showers", "rain"),
    85: ("Snow showers", "snow"),
    86: ("Snow showers", "snow"),
    95: ("Thunderstorm", "storm"),
    96: ("Thunderstorm, hail", "storm"),
    99: ("Thunderstorm, hail", "storm"),
}


def describe(code: int) -> tuple[str, str]:
    return WMO_CODES.get(code, ("Unknown", "cloudy"))


async def geocode(client: httpx.AsyncClient, city: str) -> dict[str, Any]:
    data = await get_json(
        client, GEOCODE_URL, {"name": city, "count": 1, "language": "en", "format": "json"}, SERVICE
    )
    results = data.get("results") or []
    if not results:
        raise NotFoundError(f"City '{city}' was not found")
    return results[0]


async def get_weather(client: httpx.AsyncClient, city: str) -> dict[str, Any]:
    place = await geocode(client, city)
    data = await get_json(
        client,
        FORECAST_URL,
        {
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
            "weather_code,wind_speed_10m,is_day",
            "hourly": "temperature_2m,precipitation_probability",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min",
            "timezone": "auto",
            "forecast_days": 7,
        },
        SERVICE,
    )
    current, hourly, daily = data["current"], data["hourly"], data["daily"]
    description, icon = describe(current["weather_code"])

    # Hourly data starts at midnight; slice the next 24 hours starting from "now".
    current_hour = current["time"][:13] + ":00"
    times: list[str] = hourly["time"]
    start = times.index(current_hour) if current_hour in times else 0
    end = start + 24

    return {
        "location": {
            "name": place["name"],
            "country": place.get("country", ""),
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "timezone": data.get("timezone", ""),
        },
        "current": {
            "time": current["time"],
            "temperature": current["temperature_2m"],
            "feels_like": current["apparent_temperature"],
            "humidity": current["relative_humidity_2m"],
            "wind_speed": current["wind_speed_10m"],
            "is_day": bool(current.get("is_day", 1)),
            "code": current["weather_code"],
            "description": description,
            "icon": icon,
        },
        "hourly": {
            "time": times[start:end],
            "temperature": hourly["temperature_2m"][start:end],
            "precipitation_probability": hourly["precipitation_probability"][start:end],
        },
        "daily": [
            {
                "date": day,
                "max": daily["temperature_2m_max"][i],
                "min": daily["temperature_2m_min"][i],
                "code": daily["weather_code"][i],
                "description": describe(daily["weather_code"][i])[0],
                "icon": describe(daily["weather_code"][i])[1],
            }
            for i, day in enumerate(daily["time"])
        ],
    }
