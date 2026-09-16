from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.core.config import settings

RESOURCE_DIR = Path(__file__).resolve().parent / "resources"
NICKNAME_WORDS_PATH = RESOURCE_DIR / "nickname_words.json"
EXAMPLE_FORBIDDEN_WORDS_PATH = RESOURCE_DIR / "forbidden_words.example.json"
PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


@lru_cache(maxsize=1)
def load_nickname_words() -> dict[str, list[str]]:
    with NICKNAME_WORDS_PATH.open(encoding="utf-8") as file:
        data = json.load(file)

    adjectives = data.get("adjectives")
    nouns = data.get("nouns")
    if not isinstance(adjectives, list) or not isinstance(nouns, list):
        raise ValueError("nickname_words.json must include adjectives and nouns lists")
    return {"adjectives": adjectives, "nouns": nouns}


@lru_cache(maxsize=1)
def load_forbidden_words() -> list[str]:
    path = _resolve_path(settings.FORBIDDEN_WORDS_PATH) if settings.FORBIDDEN_WORDS_PATH else EXAMPLE_FORBIDDEN_WORDS_PATH
    if settings.APP_ENV == "prod" and not settings.FORBIDDEN_WORDS_PATH:
        raise RuntimeError("FORBIDDEN_WORDS_PATH is required in production")
    if not path.exists():
        raise FileNotFoundError(f"Forbidden words file not found: {path}")

    with path.open(encoding="utf-8") as file:
        data = json.load(file)

    forbidden_words = data.get("forbidden_words")
    if not isinstance(forbidden_words, list):
        raise ValueError("forbidden_words JSON must include forbidden_words list")
    return [str(word) for word in forbidden_words if str(word)]
