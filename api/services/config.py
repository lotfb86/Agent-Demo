from __future__ import annotations

import json as _json
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: Optional[str] = None
    claude_model: str = "claude-sonnet-4-20250514"
    use_real_llm: bool = False
    openrouter_api_key: Optional[str] = None
    openrouter_model: str = "anthropic/claude-3.7-sonnet"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_timeout_seconds: float = 45.0
    database_path: str = "./data/rpmx.db"
    api_port: int = 8000
    frontend_url: str = "http://localhost:5173"
    skills_dir: str = "./agents"

    # Cost multiplier: projected cost = raw_api_cost * multiplier
    cost_multiplier_global: float = 3.0
    cost_multiplier_overrides: str = ""  # JSON, e.g. {"po_match": 5.0}

    @property
    def resolved_database_path(self) -> Path:
        path = Path(self.database_path)
        if path.is_absolute():
            return path
        return Path(__file__).resolve().parents[2] / path

    @property
    def resolved_skills_dir(self) -> Path:
        path = Path(self.skills_dir)
        if path.is_absolute():
            return path
        return Path(__file__).resolve().parents[2] / path

    @property
    def agent_cost_multipliers(self) -> dict[str, float]:
        if not self.cost_multiplier_overrides:
            return {}
        try:
            return _json.loads(self.cost_multiplier_overrides)
        except _json.JSONDecodeError:
            return {}

    def get_multiplier(self, agent_id: str) -> float:
        overrides = self.agent_cost_multipliers
        return overrides.get(agent_id, self.cost_multiplier_global)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
