"""Memory Wall — FastAPI backend."""

from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import json
import pathlib

from shared import get_db, get_embedding, cosine_similarity, _drop_emb, load_api_key

# ── Config ──
_BASE_DIR: pathlib.Path = pathlib.Path(__file__).resolve().parent.parent
_DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
_DEEPSEEK_API_KEY: str = load_api_key()

# ── Pydantic models ──

class NoteCreate(BaseModel):
    title: str = ""
    content: str = ""
    tag: str = "默认"

class NoteUpdate(BaseModel):
    title: str = ""
    content: str = ""
    tag: str = "默认"

class ChatRequest(BaseModel):
    message: str = ""
    history: list[dict] = []

# ── Embedding helpers ──

def _compute_embedding(text: str) -> Optional[list[float]]:
    emb = get_embedding(text)
    if not emb:
        return None
    if all(v == 0.0 for v in emb):
        return None
    return emb


def _vector_search(q: str, top_k: int = 10) -> list[dict]:
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

# ── DeepSeek client ──

from openai import OpenAI  # noqa: E402

_ds_client: Optional[OpenAI] = None


def _get_ds_client() -> Optional[OpenAI]:
    global _ds_client
    if _ds_client is None and _DEEPSEEK_API_KEY:
        _ds_client = OpenAI(api_key=_DEEPSEEK_API_KEY, base_url=_DEEPSEEK_BASE_URL)
    return _ds_client


_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_notes",
        "description": "在用户的笔记库中搜索相关内容。回答跟笔记相关的问题时必须先调这个工具。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词，用和笔记相同的语言"}
            },
            "required": ["query"],
        },
    },
}


def _sse(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"


def _chat_gen(body: dict):
    client = _get_ds_client()
    if not client:
        yield _sse("error", "AI 未配置（缺少 API Key）")
        return

    message = body.get("message", "").strip()
    history = body.get("history", [])
    if not message:
        yield _sse("error", "消息不能为空")
        return

    messages = [
        {
            "role": "system",
            "content": (
                "你是一个笔记助手。回答跟用户笔记相关的问题时，先调 search_notes 搜索笔记，再根据笔记内容回答。"
                "回答要简洁有条理，用中文。如果笔记内容不足以回答问题，如实说不知道。"
            ),
        }
    ]
    for h in history[-10:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": message})

    yield _sse("status", "思考中……")

    try:
        resp = client.chat.completions.create(
            model="deepseek-v4-flash",
            messages=messages,
            tools=[_SEARCH_TOOL],
            tool_choice="auto",
        )
    except Exception as e:
        yield _sse("error", f"AI 调用失败：{e}")
        return

    choice = resp.choices[0]

    if choice.finish_reason == "tool_calls":
        for tc in choice.message.tool_calls:
            if tc.function.name == "search_notes":
                args = json.loads(tc.function.arguments)
                yield _sse("status", f"在笔记中搜索: {args['query']}")
                results = _vector_search(args["query"])
                messages.append(choice.message)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(
                            [
                                {
                                    "id": r["id"],
                                    "title": r.get("title", ""),
                                    "content": r["content"],
                                    "tag": r.get("tag", ""),
                                }
                                for r in results
                            ],
                            ensure_ascii=False,
                        ),
                    }
                )

        yield _sse("status", "生成回答……")
        stream = client.chat.completions.create(
            model="deepseek-v4-flash",
            messages=messages,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield _sse("token", chunk.choices[0].delta.content)
    else:
        yield _sse("status", "生成回答……")
        stream = client.chat.completions.create(
            model="deepseek-v4-flash",
            messages=messages,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield _sse("token", chunk.choices[0].delta.content)

    yield _sse("done", "")


# ── Lifecycle ──

@asynccontextmanager
async def _lifespan(app: FastAPI):
    db = get_db()
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

    rows = db.execute(
        "SELECT * FROM notes WHERE embedding IS NULL OR embedding = ''"
    ).fetchall()
    if rows:
        print(f"Backfilling {len(rows)} embeddings...")
        for r in rows:
            text = (r["title"] or "") + " " + r["content"]
            emb = get_embedding(text)
            if emb:
                db.execute(
                    "UPDATE notes SET embedding=? WHERE id=?",
                    (json.dumps(emb), r["id"]),
                )
                db.commit()
        print("Backfill done.")
    db.close()
    yield


# ── App ──

app = FastAPI(lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── API Routes ──

@app.get("/notes")
def list_notes(page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=200)):
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
    offset = (page - 1) * limit
    rows = db.execute(
        "SELECT * FROM notes ORDER BY id DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    db.close()
    return {
        "notes": [_drop_emb(n) for n in rows],
        "total": total,
        "page": page,
        "limit": limit,
    }


@app.post("/notes", status_code=201)
def create_note(body: NoteCreate):
    text = (body.title or "") + " " + body.content
    emb = _compute_embedding(text)
    import time
    ts = int(time.time() * 1000)
    db = get_db()
    cur = db.execute(
        "INSERT INTO notes (title, content, tag, time, embedding) VALUES (?, ?, ?, ?, ?)",
        (body.title, body.content, body.tag, ts, json.dumps(emb) if emb else None),
    )
    db.commit()
    note_id = cur.lastrowid
    db.close()
    return {"id": note_id, "title": body.title, "content": body.content, "tag": body.tag, "time": ts}


@app.put("/notes/{note_id}")
def update_note(note_id: int, body: NoteUpdate):
    db = get_db()
    existing = db.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
    if not existing:
        db.close()
        raise HTTPException(status_code=404, detail="笔记不存在")
    text = (body.title or "") + " " + body.content
    emb = _compute_embedding(text)
    db.execute(
        "UPDATE notes SET title=?, content=?, tag=?, embedding=? WHERE id=?",
        (body.title, body.content, body.tag, json.dumps(emb) if emb else None, note_id),
    )
    db.commit()
    db.close()
    return {"ok": True}


@app.delete("/notes/{note_id}")
def delete_note(note_id: int):
    db = get_db()
    existing = db.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
    if not existing:
        db.close()
        raise HTTPException(status_code=404, detail="笔记不存在")
    db.execute("DELETE FROM notes WHERE id=?", (note_id,))
    db.commit()
    db.close()
    return {"ok": True}


@app.get("/search/vector")
def vector_search(q: str = Query(...), top_k: int = 20):
    emb = get_embedding(q)
    if not emb:
        return {"results": [], "error": "AI 搜索不可用"}
    db = get_db()
    rows = db.execute("SELECT * FROM notes").fetchall()
    scored: list[tuple[float, dict]] = []
    for r in rows:
        stored = r["embedding"]
        if not stored:
            continue
        sim = cosine_similarity(emb, json.loads(stored))
        scored.append((sim, dict(r)))
    scored.sort(key=lambda x: -x[0])
    results = [dict(r, score=round(s, 4)) for s, r in scored[:top_k]]
    db.close()
    return {"results": results}


@app.post("/chat")
async def chat(body: ChatRequest):
    return StreamingResponse(
        _chat_gen(body.model_dump()), media_type="text/event-stream"
    )


# ── Exception handler ──

@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": "服务器内部错误", "detail": str(exc)},
    )


# ── Static files ──

@app.get("/", include_in_schema=False)
async def serve_frontend():
    return FileResponse(_BASE_DIR / "记忆墙.html")


app.mount("/", StaticFiles(directory=str(_BASE_DIR), html=False), name="static")
