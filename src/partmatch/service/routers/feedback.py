"""フィードバック（誤判定修正・再学習データ源）と履歴。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends

from ..schemas import FeedbackIn
from ..state import AppState, get_state

router = APIRouter(prefix="/api/v1", tags=["feedback"])


@router.post("/feedback")
def add_feedback(body: FeedbackIn, state: AppState = Depends(get_state)):
    fid = state.repo.add_feedback(
        body.inspection_log_id, body.correct_part_no, body.feedback_type,
        body.comment, body.created_by)
    return {"id": fid}


@router.get("/feedback")
def list_feedback(limit: int = 100, state: AppState = Depends(get_state)):
    return {"feedback": state.repo.list_feedback(limit)}


@router.get("/history")
def history(limit: int = 100, result: Optional[str] = None,
            state: AppState = Depends(get_state)):
    return {"logs": state.repo.list_inspections(limit, result)}


@router.get("/stats")
def stats(state: AppState = Depends(get_state)):
    return state.repo.stats()
