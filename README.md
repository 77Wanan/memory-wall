<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/77Wanan/memory-wall/main/memory-wall/icon.svg">
    <img src="memory-wall/icon.svg" width="96" alt="记忆墙 logo">
  </picture>
</p>

<h1 align="center">记忆 · 墙</h1>

<p align="center">
  全栈 PWA 笔记应用 · 离线可用 · AI 语义搜索 · 昼夜自转
</p>

<p align="center">
  <img src="https://img.shields.io/badge/前端-原生_JS-3178C6?style=flat-square">
  <img src="https://img.shields.io/badge/后端-FastAPI-009688?style=flat-square">
  <img src="https://img.shields.io/badge/数据库-SQLite-003B57?style=flat-square">
  <img src="https://img.shields.io/badge/AI-DeepSeek-4F46E5?style=flat-square">
</p>

---

## 功能

- **写记忆** — 短文/长文两种输入模式，支持标题和标签分类
- **离线可用** — Service Worker 缓存，无网也能看已加载的笔记
- **昼夜主题** — 莫兰迪色系，点击切换日间/夜间模式
- **标签分组** — 默认 / 学习 / 日常 / 技术 / 灵感 / 心情，按标签分栏展示
- **语义搜索** — 接入 DeepSeek Embedding 实现向量检索，语义匹配而非关键词
- **加载更多** — 后端分页 + 前端渐进加载
- **草稿保护** — 输入内容自动存入 localStorage，误刷新可恢复
- **导入/导出** — 全量 JSON 备份与恢复
- **AI 助手** — 基于 DeepSeek 的对话式笔记搜索（Streaming SSE）
- **PWA 可安装** — manifest.json + Service Worker，支持添加到桌面

## 快速开始

```bash
# 克隆
git clone https://github.com/77Wanan/memory-wall.git
cd memory-wall

# 安装依赖
pip install fastapi uvicorn openai pydantic

# 配置 API Key（可选，仅语义搜索和 AI 助手需要）
echo "DEEPSEEK_API_KEY=sk-your-key" > backend/.env

# 启动
python -m uvicorn backend.main:app --port 8000
```

打开 `http://localhost:8000` 即可使用。

## 项目结构

```
memory-wall/
├── 记忆墙.html          # 主页面骨架
├── app.js               # 前端逻辑
├── style.css            # 样式（莫兰迪主题）
├── sw.js                # Service Worker（缓存策略）
├── manifest.json        # PWA 配置
├── icon.svg             # 应用图标
├── backend/
│   ├── main.py          # FastAPI 应用 + API 路由
│   ├── shared.py        # DB 连接 / 向量 / 工具函数
│   ├── mcp_server.py    # MCP 服务（AI 工具调用）
│   └── .env.example     # API Key 模板
├── test/
│   ├── test_api.py      # API 接口测试（21 项）
│   └── test_shared.py   # 工具函数测试
├── pyproject.toml       # 项目配置 / lint / test
└── .github/workflows/   # CI（ruff + pytest）
```

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/notes?page=&limit=` | 获取笔记列表（分页） |
| POST | `/notes` | 新增笔记 |
| PUT | `/notes/{id}` | 编辑笔记 |
| DELETE | `/notes/{id}` | 删除笔记 |
| GET | `/search/vector?q=` | 语义搜索 |
| POST | `/chat` | AI 对话（SSE 流式） |

请求/响应体均为 JSON，详情见 [main.py](backend/main.py) 中的 Pydantic 模型。

## 技术栈

| 层 | 选型 |
|------|------|
| 前端 | 原生 HTML/CSS/JS，零依赖 |
| 后端 | FastAPI + Pydantic |
| 数据库 | SQLite（WAL 模式） |
| AI 搜索 | DeepSeek Embedding |
| AI 对话 | DeepSeek Chat（Tool-use + SSE） |
| 缓存 | Service Worker（network-first） |
| CI | GitHub Actions（ruff + pytest） |

## License

MIT
