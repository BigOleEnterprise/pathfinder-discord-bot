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
    discord_guild_ids: str = ""  # Optional: comma-separated guild IDs for faster dev command sync

    @property
    def guild_id_list(self) -> list[int]:
        """Parse comma-separated guild IDs into list of integers."""
        if not self.discord_guild_ids:
            return []
        return [int(gid.strip()) for gid in self.discord_guild_ids.split(",") if gid.strip()]

    # Anthropic Claude
    anthropic_api_key: str
    anthropic_model: str = "claude-3-5-sonnet-20240620"

    # OpenAI (for embeddings)
    openai_api_key: str
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
