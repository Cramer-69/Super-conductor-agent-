"""
Configuration management for Conductor Agent.
Loads settings from environment variables and .env file.

OPENAI_API_KEY must be set in the environment (or in a local .env file).
The application will refuse to start if this key is absent.
"""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # LLM API Keys
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    perplexity_api_key: Optional[str] = None
    xai_api_key: Optional[str] = None

    @model_validator(mode="after")
    def _require_openai_api_key(self) -> "Settings":
        """Fail fast with a clear message when OPENAI_API_KEY is not configured."""
        key = (self.openai_api_key or "").strip()
        if not key or key == "your_openai_api_key_here":
            raise ValueError(
                "\n\nOPENAI_API_KEY is not set.\n"
                "  • Local development : copy .env.example → .env and add your key.\n"
                "  • Docker            : pass -e OPENAI_API_KEY=sk-... (or --env-file .env).\n"
                "  • Cloud Run / GCP   : mount the secret with --set-secrets "
                "OPENAI_API_KEY=openai-api-key:latest\n"
                "See README.md for full instructions.\n"
            )
        return self
    
    # Model Configuration
    conductor_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    
    # Vector Database
    chroma_persist_dir: str = "./data/chroma_db"
    conversations_collection: str = "conversations"
    code_collection: str = "code_snippets"
    decisions_collection: str = "decisions"
    solutions_collection: str = "solutions"
    
    # Data Processing
    chunk_size: int = 1000
    chunk_overlap: int = 200
    top_k: int = 5
    
    # API Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False
    
    # Data Paths
    raw_data_dir: str = "./data/raw"
    processed_data_dir: str = "./data/processed"
    antigravity_brain_dir: str = "C:/Users/jjc29/.gemini/antigravity/brain"
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "./logs/conductor.log"
    
    def get_base_path(self) -> Path:
        """Get the base path of the conductor_agent directory."""
        return Path(__file__).parent.parent
    
    def get_chroma_path(self) -> Path:
        """Get absolute path to ChromaDB persistence directory."""
        base = self.get_base_path()
        return base / self.chroma_persist_dir
    
    def get_raw_data_path(self) -> Path:
        """Get absolute path to raw data directory."""
        base = self.get_base_path()
        return base / self.raw_data_dir
    
    def get_processed_data_path(self) -> Path:
        """Get absolute path to processed data directory."""
        base = self.get_base_path()
        return base / self.processed_data_dir
    
    def validate_api_keys(self) -> bool:
        """Check if at least one LLM API key is configured."""
        return any([
            self.openai_api_key,
            self.anthropic_api_key,
            self.google_api_key
        ])


# Global settings instance
settings = Settings()


# Ensure required directories exist
def init_directories():
    """Create necessary directories if they don't exist."""
    base = settings.get_base_path()
    
    dirs_to_create = [
        base / "data",
        base / "data" / "raw",
        base / "data" / "processed",
        base / "data" / "chroma_db",
        base / "logs",
    ]
    
    for dir_path in dirs_to_create:
        dir_path.mkdir(parents=True, exist_ok=True)


# Initialize on import
init_directories()
