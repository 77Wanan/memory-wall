"""MCP server for 记忆墙 — 让 Claude 可以直接读写你的笔记。

启动方式：python mcp_server.py
注册到 Claude Code 后，在对话里就能直接操作笔记。
"""

import json
from mcp.server import Server
import mcp.server.stdio
import mcp.types as types
from shared import get_db, vector_search, _drop_emb, get_embedding

server = Server("memory-wall")

_TOOLS = [
    types.Tool(
        name="list_notes",
        description="列出所有笔记，可按标签筛选",
        inputSchema={
            "type": "object",
            "properties": {
                "tag": {"type": "string", "description": "筛选的标签（默认/学习/日常/技术/灵感/心情），不传返回全部"}
            },
        },
    ),
    types.Tool(
        name="get_note",
        description="根据 ID 获取单条笔记",
        inputSchema={
            "type": "object",
            "properties": {
                "note_id": {"type": "integer", "description": "笔记 ID"}
            },
            "required": ["note_id"],
        },
    ),
    types.Tool(
        name="search_notes",
        description="语义搜索笔记内容，根据含义匹配而非关键词",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "top_k": {"type": "integer", "description": "返回数量，默认 10"},
            },
            "required": ["query"],
        },
    ),
    types.Tool(
        name="create_note",
        description="创建一条新笔记",
        inputSchema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "标题（可选）"},
                "content": {"type": "string", "description": "内容"},
                "tag": {"type": "string", "description": "标签，默认'默认'"},
            },
            "required": ["content"],
        },
    ),
    types.Tool(
        name="update_note",
        description="更新一条已有笔记",
        inputSchema={
            "type": "object",
            "properties": {
                "note_id": {"type": "integer", "description": "笔记 ID"},
                "title": {"type": "string", "description": "新标题"},
                "content": {"type": "string", "description": "新内容"},
                "tag": {"type": "string", "description": "新标签"},
            },
            "required": ["note_id"],
        },
    ),
    types.Tool(
        name="delete_note",
        description="删除一条笔记",
        inputSchema={
            "type": "object",
            "properties": {
                "note_id": {"type": "integer", "description": "要删除的笔记 ID"},
            },
            "required": ["note_id"],
        },
    ),
]


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return _TOOLS


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "list_notes":
        tag = arguments.get("tag")
        db = get_db()
        if tag:
            rows = db.execute(
                "SELECT * FROM notes WHERE tag=? ORDER BY id DESC", (tag,)
            ).fetchall()
        else:
            rows = db.execute("SELECT * FROM notes ORDER BY id DESC").fetchall()
        db.close()
        return [types.TextContent(type="text", text=json.dumps([_drop_emb(r) for r in rows], ensure_ascii=False))]

    if name == "get_note":
        db = get_db()
        row = db.execute("SELECT * FROM notes WHERE id=?", (arguments["note_id"],)).fetchone()
        db.close()
        if not row:
            return [types.TextContent(type="text", text="笔记不存在")]
        return [types.TextContent(type="text", text=json.dumps(_drop_emb(row), ensure_ascii=False))]

    if name == "search_notes":
        results = vector_search(arguments["query"], arguments.get("top_k", 10))
        return [types.TextContent(type="text", text=json.dumps(results, ensure_ascii=False))]

    if name == "create_note":
        title = arguments.get("title", "")
        content = arguments["content"]
        tag = arguments.get("tag", "默认")
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
        return [types.TextContent(type="text", text=json.dumps({"id": note_id, "title": title, "content": content, "tag": tag, "time": time}, ensure_ascii=False))]

    if name == "update_note":
        note_id = arguments["note_id"]
        db = get_db()
        old = db.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
        if not old:
            db.close()
            return [types.TextContent(type="text", text="笔记不存在")]
        title = arguments.get("title", old["title"])
        content = arguments.get("content", old["content"])
        tag = arguments.get("tag", old["tag"])
        text = (title or "") + " " + content
        emb = get_embedding(text)
        db.execute(
            "UPDATE notes SET title=?, content=?, tag=?, embedding=? WHERE id=?",
            (title, content, tag, json.dumps(emb) if emb else None, note_id),
        )
        db.commit()
        db.close()
        return [types.TextContent(type="text", text="ok")]

    if name == "delete_note":
        db = get_db()
        db.execute("DELETE FROM notes WHERE id=?", (arguments["note_id"],))
        db.commit()
        db.close()
        return [types.TextContent(type="text", text="ok")]

    raise ValueError(f"未知工具: {name}")


async def main():
    async with mcp.server.stdio.stdio_server() as streams:
        read_stream, write_stream = streams
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
