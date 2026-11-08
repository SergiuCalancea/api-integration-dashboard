"""Application settings loaded from environment variables (.env supported)."""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    telegram_chat_id: str = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", ""))
    cache_ttl_seconds: int = field(default_factory=lambda: int(os.getenv("CACHE_TTL_SECONDS", "300")))
    default_city: str = field(default_factory=lambda: os.getenv("DEFAULT_CITY", "Chisinau"))
    request_timeout: float = field(default_factory=lambda: float(os.getenv("REQUEST_TIMEOUT", "10")))

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)


settings = Settings()
