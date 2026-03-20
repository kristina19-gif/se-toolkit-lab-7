from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_env_file() -> None:
    candidates = [
        Path.cwd() / ".env.bot.secret",
        Path(__file__).resolve().parents[1] / ".env.bot.secret",
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        for raw_line in candidate.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())
        return


@dataclass(slots=True)
class BotConfig:
    bot_token: str | None
    lms_api_url: str
    lms_api_key: str
    llm_api_key: str | None
    llm_api_base_url: str
    llm_api_model: str

    @classmethod
    def load(cls) -> "BotConfig":
        _load_env_file()
        return cls(
            bot_token=os.environ.get("BOT_TOKEN"),
            lms_api_url=os.environ.get("LMS_API_URL", "http://localhost:42002"),
            lms_api_key=os.environ.get("LMS_API_KEY", ""),
            llm_api_key=os.environ.get("LLM_API_KEY"),
            llm_api_base_url=os.environ.get(
                "LLM_API_BASE_URL", "http://localhost:42005/v1"
            ),
            llm_api_model=os.environ.get("LLM_API_MODEL", "coder-model"),
        )

    def require_bot_token(self) -> str:
        if not self.bot_token:
            raise RuntimeError("BOT_TOKEN is required for Telegram mode.")
        return self.bot_token

    def require_lms_api_key(self) -> str:
        if not self.lms_api_key:
            raise RuntimeError("LMS_API_KEY is required.")
        return self.lms_api_key
