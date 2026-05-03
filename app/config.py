from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


@dataclass(frozen=True)
class Settings:
    app_name: str = "Resume Optimizer Agent"
    xiaomi_api_key: str = os.getenv("XIAOMI_API_KEY", "")
    xiaomi_base_url: str = os.getenv("XIAOMI_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")
    xiaomi_model: str = os.getenv("XIAOMI_MODEL", "mimo-v2.5-pro")
    request_timeout: int = int(os.getenv("LLM_TIMEOUT", "60"))
    host: str = os.getenv("APP_HOST", "0.0.0.0")
    port: int = int(os.getenv("APP_PORT", "8000"))

    @property
    def is_llm_configured(self) -> bool:
        return bool(self.xiaomi_api_key.strip())


settings = Settings()
