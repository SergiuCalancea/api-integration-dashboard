"""Telegram Bot API integration: sends a formatted digest to a chat."""

from html import escape
from typing import Any

import httpx

from .http import UpstreamError

SERVICE = "Telegram"


def build_digest(weather: dict[str, Any], rates: dict[str, Any], crypto: list[dict[str, Any]]) -> str:
    """Build an HTML-formatted message that summarises all dashboard data."""
    loc = weather["location"]
    cur = weather["current"]
    lines = [
        "<b>🌍 Global Pulse — daily digest</b>",
        "",
        f"<b>Weather in {escape(loc['name'])}, {escape(loc['country'])}</b>",
        f"{cur['temperature']:.1f}°C, {escape(cur['description'])} "
        f"(feels like {cur['feels_like']:.1f}°C, wind {cur['wind_speed']:.0f} km/h)",
        "",
        f"<b>Exchange rates (1 {escape(rates['base'])})</b>",
    ]
    for symbol, value in rates["rates"].items():
        change = rates["change_pct"].get(symbol)
        trend = "" if change is None else f"  ({change:+.2f}%)"
        lines.append(f"• {escape(symbol)}: {value:.4f}{trend}")
    if crypto:
        lines += ["", "<b>Crypto</b>"]
        for coin in crypto:
            change = coin["change_24h"]
            trend = "" if change is None else f"  ({change:+.2f}% 24h)"
            lines.append(f"• {escape(coin['id'].title())}: ${coin['price']:,.2f}{trend}")
    return "\n".join(lines)


async def send_message(client: httpx.AsyncClient, token: str, chat_id: str, text: str) -> None:
    # Note: errors are re-raised with our own message so the bot token
    # (which is part of the URL) never leaks into logs or API responses.
    try:
        response = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        )
    except httpx.RequestError:
        raise UpstreamError(SERVICE, "Could not reach Telegram") from None
    if response.status_code != 200:
        try:
            reason = response.json().get("description", "")
        except ValueError:
            reason = ""
        raise UpstreamError(SERVICE, f"Telegram rejected the message: {reason or response.status_code}")
