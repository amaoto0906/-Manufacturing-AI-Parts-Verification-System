# 部品照合システム API（CPU）
FROM python:3.12-slim

WORKDIR /app

# 依存（CPU版 torch/torchvision を明示インデックスから）
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

COPY src ./src
COPY web ./web
COPY pyproject.toml ./

ENV PYTHONPATH=/app/src \
    PARTMATCH_BACKEND=torchvision \
    PARTMATCH_DATA_DIR=/data/data \
    PARTMATCH_MODELS_DIR=/data/models \
    PARTMATCH_DB_PATH=/data/partmatch.db \
    PARTMATCH_INDEX_PATH=/data/models/index.faiss \
    PARTMATCH_PROJECTION_PATH=/data/models/projection.npz

VOLUME ["/data"]
EXPOSE 8077

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8077/health').status==200 else 1)"

CMD ["python", "-m", "uvicorn", "partmatch.service.app:app", "--host", "0.0.0.0", "--port", "8077"]
