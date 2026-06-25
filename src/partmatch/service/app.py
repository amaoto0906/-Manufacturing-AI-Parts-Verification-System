"""FastAPI アプリケーション本体。

既存 C# システムからは本 API（REST / multipart）を呼び出す。低遅延が必要な
場合は gRPC 化や ONNX/TensorRT 最適化を追加する設計（docs/04_api_spec.md 参照）。
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from ..config import PROJECT_ROOT
from .routers import admin, feedback, health, inspect, ops, parts
from .state import get_state

# React(Vite) のビルド成果物があればそれを配信し、無ければ従来のバニラ UI(web/) を配信する。
_FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
_LEGACY_WEB = PROJECT_ROOT / "web"
WEB_DIR = _FRONTEND_DIST if (_FRONTEND_DIST / "index.html").exists() else _LEGACY_WEB


def create_app() -> FastAPI:
    app = FastAPI(
        title="部品照合システム API",
        version="0.1.0",
        description="金属プレス部品を画像で照合し、出荷時の品番取り違えを防ぐ AI 照合 API。",
    )
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(inspect.router)
    app.include_router(parts.router)
    app.include_router(admin.router)
    app.include_router(feedback.router)
    app.include_router(ops.router)

    @app.on_event("startup")
    def _startup() -> None:
        # 起動時に状態を初期化（索引があればロード）
        get_state()

    # 管理 UI（静的ファイル）
    if WEB_DIR.exists():
        app.mount("/ui", StaticFiles(directory=str(WEB_DIR), html=True), name="ui")

    @app.get("/", include_in_schema=False)
    def root():
        if WEB_DIR.exists():
            return RedirectResponse(url="/ui/")
        return {"message": "部品照合システム API. /docs を参照。"}

    return app


app = create_app()
