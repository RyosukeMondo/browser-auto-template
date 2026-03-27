"""Configuration management with environment variable support."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_prefix="BRA_", env_file=".env")

    # AI Agent Mode: "API" or "SUBSCRIPTION"
    # - API: Uses Anthropic API with api key (pay per token)
    # - SUBSCRIPTION: Uses Claude Code/Max subscription (tools run locally, no API calls)
    agent_mode: str = Field(default="SUBSCRIPTION", description="Agent mode: API or SUBSCRIPTION")
    anthropic_api_key: str = Field(default="", description="Anthropic API key (only for API mode)")
    model: str = Field(default="claude-sonnet-4-20250514", description="Claude model (only for API mode)")

    # Proxy
    proxy_host: str = Field(default="127.0.0.1", description="Proxy listen host")
    proxy_port: int = Field(default=8080, description="Proxy listen port")

    # Browser
    browser_type: str = Field(default="chromium", description="Browser: chromium, firefox, webkit")
    headless: bool = Field(default=False, description="Run browser in headless mode")

    # Storage
    data_dir: Path = Field(default=Path("./data"), description="Data storage directory")
    db_path: Path = Field(default=Path("./data/research.db"), description="SQLite database path")

    # CDP
    cdp_port: int = Field(default=9222, description="Chrome DevTools Protocol port")


settings = Settings()
