"""品番マスタ管理。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..schemas import PartUpsert
from ..state import AppState, get_state

router = APIRouter(prefix="/api/v1/parts", tags=["parts"])


@router.get("")
def list_parts(limit: int = 1000, state: AppState = Depends(get_state)):
    return {"parts": state.repo.list_parts(limit)}


@router.get("/{part_no}")
def get_part(part_no: str, state: AppState = Depends(get_state)):
    p = state.repo.get_part(part_no)
    if not p:
        raise HTTPException(404, "品番が見つかりません。")
    return p


@router.post("")
def upsert_part(body: PartUpsert, state: AppState = Depends(get_state)):
    pid = state.repo.upsert_part(
        body.part_no, body.part_name, body.category, body.material,
        body.group_id, body.status, body.accept_threshold, body.margin_threshold)
    # しきい値変更をエンジンに反映
    if state.engine is not None:
        state.engine.part_thresholds = state.repo.part_thresholds()
    return {"id": pid, "part_no": body.part_no}
