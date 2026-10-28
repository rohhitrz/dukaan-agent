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
    openai_model: str = "gpt-6-luna"
    # Reasoning models reject function tools in /v1/chat/completions unless this is
    # "none". Left unset, nothing is sent and the model's own default applies.
    openai_reasoning_effort: str | None = None
    max_tool_iterations: int = 6
    log_level: str = "INFO"

    # --- Phase 1: tracing ---
    # Keys come from docker-compose.yml's LANGFUSE_INIT_* block. Leave them blank
    # and tracing turns itself off (see app/tracing.py).
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3100"
    # Langfuse filters traces by environment and groups them by release, so later
    # phases can sit in the same project without polluting Phase 1's numbers.
    langfuse_environment: str = "local"
    langfuse_release: str = "phase-1"
    # USD per 1M tokens. Langfuse computes cost itself for models it knows; set
    # these when it doesn't recognise the model and the cost column stays empty.
    price_per_1m_input: float = 0.0
    price_per_1m_output: float = 0.0

    db_path: Path = ROOT / "data" / "dukaan.db"
    seed_path: Path = ROOT / "data" / "seed.sql"
    policies_dir: Path = ROOT / "data" / "policies"
    static_dir: Path = ROOT / "static"


settings = Settings()
