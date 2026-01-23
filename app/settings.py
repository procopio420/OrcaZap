"""Application settings and configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    # Database
    database_url: str

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Application
    secret_key: str
    debug: bool = False
    environment: str = "development"

    # WhatsApp Cloud API
    whatsapp_verify_token: str
    whatsapp_access_token: str = ""  # Optional for local dev
    whatsapp_phone_number_id: str = ""  # Optional for local dev
    whatsapp_business_account_id: str = ""  # Optional for local dev

    # Security
    bcrypt_rounds: int = 12
    admin_session_secret: str = ""  # Optional for local dev

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Allow extra env vars (e.g., OPERATOR_USERNAME, OPERATOR_PASSWORD)
    )


settings = Settings()

