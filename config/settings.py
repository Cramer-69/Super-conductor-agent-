"""
Configuration management for Conductor Agent.
Loads settings from environment variables and .env file.
"""

import logging
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


_PLACEHOLDER_KEYS = {
    "your_openai_api_key_here",
    "sk-your-key-here",
    "sk-your-actual-key-here",
}


def validate_startup_config() -> None:
    """
    Validate required environment variables at startup.
    Logs clear error messages for missing or misconfigured values.
    Does NOT exit the process – callers decide whether the error is fatal.
    """
    _log = logging.getLogger(__name__)

    if not settings.validate_api_keys():
        _log.error(
            "CONFIGURATION ERROR: No LLM API key found. "
            "Set at least one of the following environment variables: "
            "OPENAI_API_KEY, ANTHROPIC_API_KEY, or GOOGLE_API_KEY. "
            "Never hardcode secrets – use a .env file locally or "
            "Google Cloud Secret Manager in production. "
            "See DEPLOYMENT.md for details."
        )

    if settings.openai_api_key and settings.openai_api_key.strip() in _PLACEHOLDER_KEYS:
        _log.error(
            "CONFIGURATION ERROR: OPENAI_API_KEY appears to be a placeholder value. "
            "Replace it with a real key from https://platform.openai.com/api-keys. "
            "If you accidentally exposed a real key, rotate it immediately at "
            "https://platform.openai.com/api-keys and never commit secrets to source control."
        )


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
validate_startup_config()
