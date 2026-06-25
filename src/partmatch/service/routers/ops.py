"""運用・設定エンドポイント: しきい値調整・画質キャリブレーション・自己診断。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...benchmark import live_self_test
from ...quality.calibrate import calibrate_demo
from ..schemas import CalibrateIn, SelfTestIn, ThresholdsIn
from ..state import AppState, get_state

router = APIRouter(prefix="/api/v1", tags=["ops"])


@router.post("/settings/thresholds")
def update_thresholds(body: ThresholdsIn, state: AppState = Depends(get_state)):
    """判定しきい値を実行時に更新する（エンジンは settings を直接参照するため即時反映）。"""
    s = state.settings
    changed = {}
    for field in ("accept_threshold", "review_threshold", "margin_threshold",
                  "similar_margin_threshold", "top_k"):
        v = getattr(body, field)
        if v is not None:
            setattr(s, field, v)
            changed[field] = v
    return {"updated": changed, "thresholds": state.info()["thresholds"]}


@router.post("/calibrate-quality")
def calibrate_quality(body: CalibrateIn, state: AppState = Depends(get_state)):
    """合成の良品/不良品から画質しきい値を導出し、保存してエンジンへ反映する。"""
    res = calibrate_demo(state.settings, save=body.save)
    if body.save:
        state.rebuild_engine()  # 新しい quality_overrides を読み込む
    return {
        "recommended": res["recommended"],
        "report": res["report"],
        "applied": body.save,
    }


@router.post("/quality-thresholds/reset")
def reset_quality(state: AppState = Depends(get_state)):
    """キャリブレーション済みしきい値を破棄し、既定値へ戻す。"""
    path = state.settings.quality_thresholds_path
    existed = path.exists()
    if existed:
        path.unlink()
        state.rebuild_engine()
    return {"reset": existed}


@router.post("/self-test")
def self_test(body: SelfTestIn, state: AppState = Depends(get_state)):
    """稼働中モデルの精度・安全性を自己診断する（再学習なし）。"""
    if not state.ready:
        raise HTTPException(409, "索引が未構築です。")
    try:
        return live_self_test(state.settings, state.engine,
                              n_parts=body.n_parts, seed=body.seed)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
