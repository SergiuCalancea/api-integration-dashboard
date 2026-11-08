"""Shared HTTP helpers and error types for all integrations."""

from typing import Any

import httpx


class UpstreamError(Exception):
    """Raised when a third-party API fails or cannot be reached."""

    def __init__(self, service: str, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.service = service
        self.message = message
        self.status_code = status_code


class NotFoundError(Exception):
    """Raised when the requested resource (e.g. a city) does not exist."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


async def get_json(
    client: httpx.AsyncClient, url: str, params: dict[str, Any] | None, service: str
) -> Any:
    """GET a JSON document and translate network/HTTP failures into UpstreamError."""
    try:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        if code == 429:
            raise UpstreamError(service, f"{service} rate limit reached, try again in a minute", 503) from exc
        raise UpstreamError(service, f"{service} returned HTTP {code}") from exc
    except httpx.RequestError as exc:
        raise UpstreamError(service, f"Could not reach {service}") from exc
    except ValueError as exc:
        raise UpstreamError(service, f"{service} returned invalid JSON") from exc
