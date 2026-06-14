FROM python:3.13-slim

WORKDIR /app

# 后端依赖
COPY memory-wall/backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# 后端 + 前端文件
COPY memory-wall/backend/ ./backend/
COPY memory-wall/记忆墙.html ./记忆墙.html
COPY memory-wall/icon.svg ./icon.svg
COPY memory-wall/manifest.json ./manifest.json
COPY memory-wall/sw.js ./sw.js
COPY memory-wall/index.html ./index.html
COPY memory-wall/assets/ ./assets/

EXPOSE 8002

CMD sh -c "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8002}"
