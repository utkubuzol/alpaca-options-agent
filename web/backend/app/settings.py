"""Backend configuration — env only, no .env of the root package involved.
Every secret is injected by the deploy platform (see web/README.md)."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Supabase
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    # Optional: HS256 legacy JWT secret. If unset we verify tokens via the
    # project JWKS (asymmetric signing keys), which new projects use by default.
    supabase_jwt_secret: str = ""

    # App-level secret used to Fernet-encrypt broker keys / bot tokens at rest.
    # Generate with: python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"
    app_secret_key: str = ""

    # Platform Telegram bot (BotFather). Per-user bot token overrides this.
    telegram_bot_token: str = ""

    # CORS — the deployed frontend origin(s), comma-separated.
    frontend_origins: str = "http://localhost:3000"

    # The account whose journal + broker feed the public landing page
    # (/api/public/showcase, /api/public/quotes). No auth required to read it.
    showcase_user_id: str = ""

    # Where the JSONL fallback journal / iv_history go when not using the DB sink.
    agent_log_root: str = "./logs"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.frontend_origins.split(",") if o.strip()]

    @property
    def jwks_url(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"

    @property
    def auth_user_url(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1/user"

    @property
    def rest_url(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/rest/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
