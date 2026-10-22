"""Settings loaded from .env.

pydantic-settings reads environment variables (and .env) and validates them into a
typed object, so a missing/misspelled key fails loudly at startup instead of as a
None halfway through a request.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    openai_api_key: str
    openai_model: str = "gpt-5.1-mini"
    max_tool_iterations: int = 6
    log_level: str = "INFO"

    db_path: Path = ROOT / "data" / "dukaan.db"
    seed_path: Path = ROOT / "data" / "seed.sql"
    policies_dir: Path = ROOT / "data" / "policies"
    static_dir: Path = ROOT / "static"


settings = Settings()
