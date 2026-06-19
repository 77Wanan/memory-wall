"""Tests for memory wall API — uses isolated temp databases."""

import sys, pathlib, os, tempfile

_backend = str(pathlib.Path(__file__).resolve().parent.parent / "backend")
if _backend not in sys.path:
    sys.path.insert(0, _backend)

os.environ["DEEPSEEK_API_KEY"] = "test-key"

import json
import pytest
from fastapi.testclient import TestClient
from main import app


# ── Fixture: fresh temp database per test function ──

@pytest.fixture
def db_path():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    p = pathlib.Path(tmp.name)
    tmp.close()
    yield p
    # Cleanup: retry a few times on Windows (file locks)
    import gc, time
    gc.collect()
    for _ in range(3):
        try:
            p.unlink(missing_ok=True)
            return
        except PermissionError:
            time.sleep(0.3)
    # Give up — OS will clean temp files eventually
    p.unlink(missing_ok=True)


@pytest.fixture
def client(db_path):
    import shared as _shared_mod
    _shared_mod._DB_PATH = db_path

    # Create tables (TestClient doesn't trigger lifespan)
    db = _shared_mod.get_db()
    db.execute(
        "CREATE TABLE IF NOT EXISTS notes ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "title TEXT, "
        "content TEXT, "
        "tag TEXT DEFAULT '默认', "
        "time INTEGER, "
        "embedding TEXT"
        ")"
    )
    cols = [c[1] for c in db.execute("PRAGMA table_info(notes)").fetchall()]
    if "embedding" not in cols:
        db.execute("ALTER TABLE notes ADD COLUMN embedding TEXT")
    db.commit()
    db.close()

    return TestClient(app)


# ── Helpers ──

def _count_notes(client):
    r = client.get("/notes")
    assert r.status_code == 200
    body = r.json()
    return len(body["notes"]), body["total"]


# ── CRUD ──

def test_list_notes_empty(client):
    """Fresh temp DB should have 0 notes."""
    r = client.get("/notes?page=1&limit=5")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    assert body["notes"] == []


def test_create_and_read(client):
    r = client.post("/notes", json={"title": "Test", "content": "Hello world", "tag": "学习"})
    assert r.status_code == 201
    note = r.json()
    assert note["title"] == "Test"
    assert note["content"] == "Hello world"
    assert note["tag"] == "学习"
    assert note["id"] > 0

    _, total = _count_notes(client)
    assert total == 1


def test_create_missing_content(client):
    """Empty content still creates a note."""
    r = client.post("/notes", json={"title": "No content"})
    assert r.status_code == 201
    assert r.json()["id"] > 0


def test_update_note(client):
    r = client.post("/notes", json={"title": "Before", "content": "Old", "tag": "默认"})
    nid = r.json()["id"]

    r2 = client.put(f"/notes/{nid}", json={"title": "After", "content": "Updated", "tag": "日常"})
    assert r2.status_code == 200

    r3 = client.get("/notes")
    updated = [n for n in r3.json()["notes"] if n["id"] == nid]
    assert len(updated) == 1
    assert updated[0]["title"] == "After"


def test_delete_note(client):
    r = client.post("/notes", json={"content": "To delete"})
    nid = r.json()["id"]

    assert client.delete(f"/notes/{nid}").status_code == 200
    assert client.delete(f"/notes/{nid}").status_code == 404


def test_delete_nonexistent(client):
    assert client.delete("/notes/999999").status_code == 404


def test_update_nonexistent(client):
    assert client.put("/notes/999999", json={"content": "Nope"}).status_code == 404


# ── Pagination ──

def test_pagination(client):
    for i in range(5):
        client.post("/notes", json={"content": f"Note {i}", "tag": "默认"})

    r1 = client.get("/notes?page=1&limit=3")
    assert r1.status_code == 200
    assert len(r1.json()["notes"]) == 3

    r2 = client.get("/notes?page=2&limit=3")
    assert r2.status_code == 200
    assert len(r2.json()["notes"]) == 2  # 5 total - 3 on page 1 = 2

    # No overlap between pages
    ids1 = {n["id"] for n in r1.json()["notes"]}
    ids2 = {n["id"] for n in r2.json()["notes"]}
    assert ids1 & ids2 == set()

    assert r1.json()["total"] == 5


# ── 404 for non-existent ──

def test_404_delete(client):
    assert client.delete("/notes/99999").status_code == 404


def test_404_update(client):
    assert client.put("/notes/99999", json={"content": "x"}).status_code == 404


# ── Validation ──

def test_invalid_page(client):
    assert client.get("/notes?page=-1").status_code == 422


def test_invalid_limit(client):
    assert client.get("/notes?limit=999").status_code == 422


# ── Search / Chat ──

def test_vector_search_no_key(client):
    """Without valid API key, search returns error."""
    r = client.get("/search/vector?q=你好")
    assert r.status_code == 200
    body = r.json()
    assert body["error"] == "AI 搜索不可用"
    assert body["results"] == []


def test_chat_no_key(client):
    """Without valid API key, chat returns SSE error."""
    r = client.post("/chat", json={"message": "你好", "history": []})
    assert r.status_code == 200
    assert "AI 调用失败" in r.text


# ── Static file serving ──

def test_frontend_html(client):
    """GET / returns the frontend HTML."""
    r = client.get("/")
    assert r.status_code == 200
    assert "记忆墙" in r.text


# ── Edge cases ──

def test_long_content(client):
    """Very long content (10k chars) should store and return correctly."""
    long = "x" * 10000
    r = client.post("/notes", json={"content": long, "tag": "默认"})
    assert r.status_code == 201

    r2 = client.get("/notes?limit=1")
    assert r2.json()["notes"][0]["content"] == long


def test_special_characters(client):
    """HTML special characters stored as-is, not stripped."""
    payload = "<script>alert('xss')</script> & \"'"
    r = client.post("/notes", json={"content": payload, "title": "x&y"})
    assert r.status_code == 201
    nid = r.json()["id"]

    r2 = client.get(f"/notes?limit=1")
    saved = r2.json()["notes"][0]
    assert saved["id"] == nid
    assert saved["content"] == payload
    assert saved["title"] == "x&y"
