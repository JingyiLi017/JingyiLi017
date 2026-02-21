from __future__ import annotations

import os
from dataclasses import dataclass


def _normalize_ollama_host(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return "http://127.0.0.1:11434"
    if raw.startswith("http://") or raw.startswith("https://"):
        if raw.startswith("http://0.0.0.0"):
            return raw.replace("http://0.0.0.0", "http://127.0.0.1", 1)
        if raw.startswith("https://0.0.0.0"):
            return raw.replace("https://0.0.0.0", "https://127.0.0.1", 1)
        return raw
    if raw.startswith("0.0.0.0"):
        raw = raw.replace("0.0.0.0", "127.0.0.1", 1)
    return f"http://{raw}"


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("ENGINE_HOST", "127.0.0.1")
    port: int = int(os.getenv("ENGINE_PORT", "17777"))
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/novel_db",
    )
    ollama_host: str = _normalize_ollama_host(os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"))
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "bge-m3:latest")


settings = Settings()
