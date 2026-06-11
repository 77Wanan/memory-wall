from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sqlite3

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    conn = sqlite3.connect("notes.db")
    conn.row_factory = sqlite3.Row
    return conn


@app.on_event("startup")
def startup():
    db = get_db()
    db.execute(
        "CREATE TABLE IF NOT EXISTS notes ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "title TEXT, "
        "content TEXT, "
        "tag TEXT DEFAULT '默认', "
        "time INTEGER"
        ")"
    )
    db.commit()
    db.close()


@app.get("/notes")
def get_notes():
    db = get_db()
    notes = db.execute("SELECT * FROM notes ORDER BY id DESC").fetchall()
    db.close()
    return {"notes": [dict(n) for n in notes]}


@app.post("/notes")
def create_note(title: str = "", content: str = "", tag: str = "默认", time: int = 0):
    db = get_db()
    if time == 0:
        time = int(__import__("time").time() * 1000)
    cur = db.execute(
        "INSERT INTO notes (title, content, tag, time) VALUES (?, ?, ?, ?)",
        (title, content, tag, time),
    )
    db.commit()
    note_id = cur.lastrowid
    db.close()
    return {"id": note_id, "title": title, "content": content, "tag": tag, "time": time}


@app.put("/notes/{note_id}")
def update_note(note_id: int, title: str = "", content: str = "", tag: str = "默认"):
    db = get_db()
    db.execute(
        "UPDATE notes SET title=?, content=?, tag=? WHERE id=?",
        (title, content, tag, note_id),
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
