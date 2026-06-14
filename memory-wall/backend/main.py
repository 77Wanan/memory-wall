from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import sqlite3, json, os, pathlib
from openai import OpenAI

from shared import get_db, get_embedding, cosine_similarity, _drop_emb, load_api_key

# === 配置 ===
_BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
_DB_PATH = _BASE_DIR / "notes.db"
_DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
_DEEPSEEK_API_KEY = load_api_key()

def _vector_search(q: str, top_k: int = 10) -> list[dict]:
    emb = get_embedding(q)
    if not emb:
        return []
    db = get_db()
    rows = db.execute("SELECT * FROM notes").fetchall()
    db.close()
    scored = []
    for r in rows:
        stored = r["embedding"]
        if not stored:
            continue
        sim = cosine_similarity(emb, json.loads(stored))
        scored.append((sim, dict(r)))
    scored.sort(key=lambda x: -x[0])
    return [_drop_emb(r) for _, r in scored[:top_k]]

# === DeepSeek 客户端 ===
_ds_client = None
def get_ds_client():
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
            "required": ["query"]
        }
    }
}

def _sse(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"

def chat_gen(body: dict):
    client = get_ds_client()
    if not client:
        yield _sse("error", "AI 未配置（缺少 API Key）")
        return

    message = body.get("message", "").strip()
    history = body.get("history", [])
    if not message:
        yield _sse("error", "消息不能为空")
        return

    messages = [{
        "role": "system",
        "content": "你是一个笔记助手。回答跟用户笔记相关的问题时，先调 search_notes 搜索笔记，再根据笔记内容回答。"
        "回答要简洁有条理，用中文。如果笔记内容不足以回答问题，如实说不知道。"
    }]
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
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(
                        [{"id": r["id"], "title": r.get("title",""), "content": r["content"], "tag": r.get("tag","")}
                         for r in results], ensure_ascii=False)
                })

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

# ===== App & Middleware =====
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    return StreamingResponse(chat_gen(body), media_type="text/event-stream")

@app.on_event("startup")
def startup():
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

@app.get("/notes")
def get_notes():
    db = get_db()
    notes = db.execute("SELECT * FROM notes ORDER BY id DESC").fetchall()
    db.close()
    return {"notes": [_drop_emb(n) for n in notes]}

@app.post("/notes")
def create_note(title: str = "", content: str = "", tag: str = "默认", time: int = 0):
    if time == 0:
        time = int(__import__("time").time() * 1000)
    text = (title or "") + " " + content
    emb = get_embedding(text)
    db = get_db()
    cur = db.execute(
        "INSERT INTO notes (title, content, tag, time, embedding) VALUES (?, ?, ?, ?, ?)",
        (title, content, tag, time, json.dumps(emb) if emb else None),
    )
    db.commit()
    note_id = cur.lastrowid
    db.close()
    return {"id": note_id, "title": title, "content": content, "tag": tag, "time": time}

@app.put("/notes/{note_id}")
def update_note(note_id: int, title: str = "", content: str = "", tag: str = "默认"):
    text = (title or "") + " " + content
    emb = get_embedding(text)
    emb_json = json.dumps(emb) if emb else None
    db = get_db()
    db.execute(
        "UPDATE notes SET title=?, content=?, tag=?, embedding=? WHERE id=?",
        (title, content, tag, emb_json, note_id),
    )
    db.commit()
    db.close()
    return {"ok": True}

@app.delete("/notes/{note_id}")
def delete_note(note_id: int):
    db = get_db()
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
    scored = []
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

# ===== Frontend Static Files =====
@app.get("/", include_in_schema=False)
async def serve_frontend():
    return FileResponse(_BASE_DIR / "记忆墙.html")

app.mount("/", StaticFiles(directory=str(_BASE_DIR), html=False), name="static")
