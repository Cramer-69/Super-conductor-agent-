"""Configuration for the Semantic Wall service — independent from the rest
of this repo's config/settings.py (separate deployable service, separate env)."""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Supabase (memory datastore) — absent means the memory layer is
    # gracefully unavailable, not a crash. Requires a real Supabase project
    # with the pgvector extension enabled (see README.md); can't be created
    # from here.
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None

    # LLM providers for the single Phase 1 agent (Claude or Grok per the
    # blueprint's Phase 1 choice; OpenAI included since it's also already
    # wired via conductor/tool_loop.py's shared loop).
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    xai_api_key: Optional[str] = None

    # Embedding model — OpenAI text-embedding-3-large per the blueprint.
    embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 3072

    # Agent
    default_agent_model_provider: str = "anthropic"  # or "openai" / "xai"
    default_agent_model: str = "claude-sonnet-5"

    # Check-in engine
    checkin_interval_minutes: int = 30

    # API server
    api_host: str = "0.0.0.0"
    api_port: int = 8090

    def is_memory_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)

    def configured_providers(self) -> list[str]:
        candidates = {
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "xai": self.xai_api_key,
        }
        return [name for name, key in candidates.items() if key]


settings = Settings()
