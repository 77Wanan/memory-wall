# 記憶 · 牆

全栈 PWA 笔记应用，支持离线缓存、昼夜模式、标签分类、导入导出。

## 技术栈

| 层 | 技术 |
|------|------|
| 前端 | 原生 HTML/CSS/JS + PWA（Service Worker） |
| 后端 | FastAPI（Python） |
| 数据库 | SQLite |
| 部署 | GitHub Pages（前端）+ 待定（后端） |

## 功能

- 笔记增删改查，按标签分组
- 全文搜索
- 昼夜主题切换
- 短文 / 长文两种输入模式
- 数据导入 / 导出（JSON）
- 离线可用（PWA Service Worker）
- 侧边栏快速导航

## 本地运行

```bash
# 1. 安装后端依赖
pip install fastapi uvicorn

# 2. 启动后端（终端 1）
python -m uvicorn backend.main:app --reload

# 3. 打开前端
# 双击 记忆墙.html 或使用浏览器打开
```

后端默认运行在 `http://127.0.0.1:8000`，前端通过 fetch 调后端 API。

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /notes | 获取所有笔记 |
| POST | /notes | 新增笔记 |
| PUT | /notes/{id} | 编辑笔记 |
| DELETE | /notes/{id} | 删除笔记 |

## 项目结构

```
記憶牆/
├── 记忆墙.html          # 主页面
├── index.html            # 入口（重定向）
├── manifest.json         # PWA 配置
├── sw.js                 # Service Worker
├── icon.svg              # 应用图标
├── backend/
│   ├── main.py           # FastAPI 后端
│   └── notes.db          # SQLite 数据库（本地生成）
└── .gitignore
```
