# 記憶 · 牆

全栈 PWA 笔记应用，支持离线缓存、昼夜模式、标签分类、导入导出、AI 语义搜索。

## 技术栈

| 层 | 技术 |
|------|------|
| 前端 | 原生 HTML/CSS/JS + PWA（Service Worker） |
| 后端 | FastAPI（Python） |
| 数据库 | SQLite |
| AI 搜索 | DeepSeek Embedding |

## 项目结构

```
D:/Claude code/
├── memory-wall/            # 記憶·牆 主项目
│   ├── 记忆墙.html          # 主页面
│   ├── index.html           # 入口（重定向）
│   ├── manifest.json        # PWA 配置
│   ├── sw.js                # Service Worker
│   ├── icon.svg             # 应用图标
│   ├── notes.db             # SQLite 数据库
│   └── backend/
│       ├── main.py          # FastAPI 后端
│       └── .env             # API Key 配置
├── netease/                 # 网易云音乐控制
├── sandbox/                 # 实验/学习项目
│   ├── fastapi_learning/
│   ├── hello_api.py
│   ├── particle-gesture.html
│   └── scan_transcripts.py
├── assets/                  # 图片素材
├── CLAUDE.md
└── README.md
```

## 本地运行

```bash
# 1. 启动后端（项目根目录）
python -m uvicorn memory-wall.backend.main:app --reload

# 2. 打开前端
# 打开 memory-wall/记忆墙.html
```

后端运行在 `http://127.0.0.1:8000`。

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /notes | 获取所有笔记 |
| POST | /notes | 新增笔记 |
| PUT | /notes/{id} | 编辑笔记 |
| DELETE | /notes/{id} | 删除笔记 |
| GET | /search/vector | AI 语义搜索 |

## 语义搜索

在搜索框旁切换到「语义」模式，输入内容即可按语义匹配笔记，需配置 DeepSeek API Key。
