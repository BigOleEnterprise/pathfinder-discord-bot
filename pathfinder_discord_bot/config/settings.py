"""Configuration settings loaded from environment variables."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Discord
    discord_bot_token: str
    discord_guild_id: int | None = None  # Optional: for faster dev command sync

    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    # MongoDB
    mongodb_uri: str = "mongodb://mongodb:27017"
    mongodb_database: str = "pathfinder_bot"

    # Bot Configuration
    log_level: str = "INFO"
    environment: str = "development"

    # Rate Limiting
    ask_rate_limit_requests: int = 5
    ask_rate_limit_window_seconds: int = 600


# Singleton instance
settings = Settings()
