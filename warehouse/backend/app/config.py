from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "WMS Almacén"
    DEBUG: bool = True

    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/warehouse_db",
        description="Async PostgreSQL connection URL",
    )

    SECRET_KEY: str = Field(
        default="change-me-in-production-secret-key-warehouse-wms",
        description="Secret key for JWT tokens",
    )

    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

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


settings = Settings()
