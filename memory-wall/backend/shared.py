"""Shared utilities for memory wall backend & MCP server."""

import sqlite3
import json
import os
import pathlib
from typing import Optional
from openai import OpenAI

_BASE_DIR: pathlib.Path = pathlib.Path(__file__).resolve().parent.parent
_DB_PATH: pathlib.Path = _BASE_DIR / "notes.db"


def get_db() -> sqlite3.Connection:
    """Get a SQLite connection with WAL mode for better concurrency."""
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def load_api_key() -> str:
    """Load DeepSeek API key from environment variable, with .env fallback."""
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key:
        return key
    _env_path = pathlib.Path(__file__).parent / ".env"
    if _env_path.exists():
        for line in _env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("DEEPSEEK_API_KEY="):
                return line.strip().split("=", 1)[1]
    return ""


_client: Optional[OpenAI] = None


def _get_client() -> Optional[OpenAI]:
    global _client
    if _client is None:
        key = load_api_key()
        if key:
            _client = OpenAI(api_key=key, base_url="https://api.deepseek.com/v1")
    return _client


def get_embedding(text: str) -> list[float]:
    """Get embedding vector for text. Returns empty list on failure."""
    client = _get_client()
    if not client:
        return []
    try:
        resp = client.embeddings.create(model="deepseek-embedding", input=text)
        return resp.data[0].embedding
    except Exception:
        return []


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    return dot / (na * nb) if na and nb else 0


def _drop_emb(n: sqlite3.Row) -> dict:
    d = dict(n)
    d.pop("embedding", None)
    return d


def vector_search(q: str, top_k: int = 10) -> list[dict]:
    emb = get_embedding(q)
    if not emb:
        return []
    db = get_db()
    rows = db.execute("SELECT * FROM notes").fetchall()
    db.close()
    scored: list[tuple[float, dict]] = []
    for r in rows:
        stored = r["embedding"]
        if not stored:
            continue
        sim = cosine_similarity(emb, json.loads(stored))
        scored.append((sim, dict(r)))
    scored.sort(key=lambda x: -x[0])
    return [_drop_emb(r) for _, r in scored[:top_k]]
