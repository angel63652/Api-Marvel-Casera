import secrets

from pydantic_settings import BaseSettings
from pydantic import Field, model_validator
from typing import Optional


# Sentinel left in older config/.env files; must never be used in production.
_INSECURE_SECRETS = {
    "",
    "change-me-in-production-secret-key-warehouse-wms",
    "cambia-esta-clave-en-produccion",
}


class Settings(BaseSettings):
    APP_NAME: str = "WMS Almacén"
    # Secure by default: production must opt INTO debug explicitly.
    DEBUG: bool = False

    # Safe local dev default (SQLite, no credentials). Production overrides via env.
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./wms.db",
        description="Async database connection URL",
    )

    # No insecure default. Must be provided in production (validated below).
    SECRET_KEY: str = Field(
        default="",
        description="Secret key for JWT tokens (required in production)",
    )

    ALGORITHM: str = "HS256"
    # Short-lived access token; long-lived revocable refresh token.
    # 60 min interim; drop to 15-30 once the frontend wires auto-refresh.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    # Rate limit for the login endpoint (SlowAPI syntax).
    LOGIN_RATE_LIMIT: str = "10/minute"

    # CORS: explicit allowlist (never "*" together with credentials).
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:8000", "http://127.0.0.1:8000"],
        description="Allowed browser origins for CORS",
    )

    # Bootstrap admin: credentials come from the environment, not the code.
    ADMIN_EMAIL: str = Field(default="admin@distrigal.com")
    ADMIN_PASSWORD: Optional[str] = Field(
        default=None,
        description="Bootstrap admin password (required to seed admin in production)",
    )

    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, description="Anthropic Claude API key")

    GMAIL_CLIENT_ID: Optional[str] = Field(default=None, description="Gmail OAuth2 client ID")
    GMAIL_CLIENT_SECRET: Optional[str] = Field(default=None, description="Gmail OAuth2 client secret")
    GMAIL_REDIRECT_URI: str = Field(
        default="http://localhost:8000/api/v1/emails/oauth-callback",
        description="Gmail OAuth2 redirect URI",
    )
    GMAIL_SCOPES: list[str] = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.modify",
    ]

    FRONTEND_STATIC_PATH: str = "../../frontend/static"
    FRONTEND_TEMPLATES_PATH: str = "../../frontend"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "case_sensitive": True}

    @model_validator(mode="after")
    def _enforce_secret(self) -> "Settings":
        """Refuse to run with an insecure SECRET_KEY in production.

        - Production (DEBUG=False): a strong, explicit SECRET_KEY is mandatory.
        - Development (DEBUG=True): if none is set, generate an ephemeral one so
          local runs work, but tokens won't survive a restart (by design).
        """
        if self.SECRET_KEY in _INSECURE_SECRETS:
            if self.DEBUG:
                self.SECRET_KEY = secrets.token_urlsafe(48)
            else:
                raise RuntimeError(
                    "SECRET_KEY no configurado o inseguro. Define una clave fuerte "
                    "(p. ej. `openssl rand -hex 32`) en la variable de entorno SECRET_KEY "
                    "antes de arrancar en producción (DEBUG=False)."
                )
        return self


settings = Settings()
