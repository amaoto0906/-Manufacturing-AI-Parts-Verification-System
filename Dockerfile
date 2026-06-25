# 部品照合システム（CPU）— React UI 同梱の単一コンテナ
# これ1つを Render / Railway / Fly.io / VM 等にデプロイすれば、
# API も管理UI(/ui) も同一URLで提供できる（Vercel 不要）。

# ---- Stage 1: React(Vite) フロントエンドをビルド ----
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build          # 既定 base=/ui/ で frontend/dist を生成

# ---- Stage 2: Python バックエンド ----
FROM python:3.12-slim
WORKDIR /app

# 依存（CPU版 torch/torchvision を明示インデックスから）
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

COPY src ./src
COPY web ./web
COPY pyproject.toml ./
# React ビルド成果物を取り込む（FastAPI が /ui で配信。無ければ web/ にフォールバック）
COPY --from=web /web/dist ./frontend/dist

ENV PYTHONPATH=/app/src \
    PARTMATCH_BACKEND=torchvision \
    PARTMATCH_DATA_DIR=/data/data \
    PARTMATCH_MODELS_DIR=/data/models \
    PARTMATCH_DB_PATH=/data/partmatch.db \
    PARTMATCH_INDEX_PATH=/data/models/index.faiss \
    PARTMATCH_PROJECTION_PATH=/data/models/projection.npz \
    PARTMATCH_QUALITY_THRESHOLDS_PATH=/data/models/quality_thresholds.json

VOLUME ["/data"]
EXPOSE 8077

# クラウドは $PORT を割り当てる場合がある（Render等）。あればそれを使う。
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import os,urllib.request,sys; p=os.environ.get('PORT','8077'); sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{p}/health').status==200 else 1)"

CMD ["sh", "-c", "python -m uvicorn partmatch.service.app:app --host 0.0.0.0 --port ${PORT:-8077}"]
