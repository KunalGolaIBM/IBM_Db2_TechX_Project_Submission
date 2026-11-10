from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db2_dsn: str | None
    cors_origins: tuple[str, ...]
    watsonx_apikey: str | None
    watsonx_project_id: str | None
    watsonx_url: str | None
    watsonx_model: str | None

    @classmethod
    def from_env(cls) -> "Settings":
        origins = tuple(
            item.strip() for item in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
            if item.strip()
        )
        return cls(
            db2_dsn=os.getenv("DB2_DSN"),
            cors_origins=origins,
            watsonx_apikey=os.getenv("WATSONX_APIKEY"),
            watsonx_project_id=os.getenv("WATSONX_PROJECT_ID"),
            watsonx_url=os.getenv("WATSONX_URL"),
            watsonx_model=os.getenv("WATSONX_MODEL"),
        )

    @property
    def llm_configured(self) -> bool:
        return all((self.watsonx_apikey, self.watsonx_project_id, self.watsonx_url, self.watsonx_model))
