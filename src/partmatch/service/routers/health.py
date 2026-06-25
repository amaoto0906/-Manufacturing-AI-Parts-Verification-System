"""ヘルスチェックと情報。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..state import AppState, get_state

router = APIRouter(tags=["health"])


@router.get("/health")
def health(state: AppState = Depends(get_state)):
    return {"status": "ok", "ready": state.ready}


@router.get("/api/v1/info")
def info(state: AppState = Depends(get_state)):
    return state.info()
