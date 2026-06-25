"""照合エンドポイント。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from ...preprocess import load_image
from ..state import AppState, get_state

router = APIRouter(prefix="/api/v1", tags=["inspect"])


@router.post("/inspect")
async def inspect(
    file: UploadFile = File(..., description="撮影画像"),
    expected_part_no: Optional[str] = Form(None, description="作業指示の期待品番"),
    operator_id: Optional[str] = Form(None),
    line_id: Optional[str] = Form(None),
    run_quality: bool = Form(True),
    state: AppState = Depends(get_state),
):
    if not state.ready:
        raise HTTPException(409, "索引が未構築です。先に /api/v1/build-index を実行してください。")
    data = await file.read()
    if not data:
        raise HTTPException(400, "空の画像です。")
    try:
        img = load_image(data)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"画像を読み込めません: {e}")

    result = state.engine.inspect(img, expected_part_no=expected_part_no,
                                  run_quality=run_quality)
    payload = result.to_dict()
    log_id = state.repo.log_inspection(
        payload, image_path=file.filename, operator_id=operator_id, line_id=line_id)
    payload["log_id"] = log_id
    return payload


@router.post("/search-similar")
async def search_similar(
    file: UploadFile = File(...),
    top_k: int = Form(5),
    state: AppState = Depends(get_state),
):
    """期待品番なしの類似検索（オープン識別）。"""
    if not state.ready:
        raise HTTPException(409, "索引が未構築です。")
    img = load_image(await file.read())
    result = state.engine.inspect(img, expected_part_no=None, run_quality=False)
    return result.to_dict()
