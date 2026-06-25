"""管理操作: 索引構築・デモデータ生成・品番マスタ同期・サンプル画像生成。"""
from __future__ import annotations

import io
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from ...data.synth import generate_dataset, generate_part_specs, render_part
from ...pipeline import build_index, load_parts_meta
from ..schemas import BuildIndexIn, GenerateDemoIn
from ..state import AppState, get_state

router = APIRouter(prefix="/api/v1", tags=["admin"])


def _gen_config_path(state: AppState):
    # generate_dataset が data_dir/metadata/gen_config.json に保存（CLI/API共通）
    return state.settings.data_dir / "metadata" / "gen_config.json"


def _sync_parts_from_metadata(state: AppState) -> int:
    """parts.csv のメタ情報を品番マスタへ反映する。"""
    meta = load_parts_meta(state.settings.data_dir / "metadata")
    for part_no, m in meta.items():
        state.repo.upsert_part(part_no, group_id=m.get("group_id"),
                               category=m.get("shape"))
    return len(meta)


@router.post("/build-index")
def build(body: BuildIndexIn, state: AppState = Depends(get_state)):
    summary = build_index(state.settings, train=body.train, epochs=body.epochs)
    _sync_parts_from_metadata(state)
    state.rebuild_engine()
    return {"summary": summary, "ready": state.ready}


@router.post("/generate-demo")
def generate_demo(body: GenerateDemoIn, state: AppState = Depends(get_state)):
    """合成データ生成 → 距離学習 → 索引構築 → 品番同期 を一括実行（デモ用）。"""
    ds = generate_dataset(state.settings.data_dir, n_parts=body.n_parts,
                          n_groups=body.n_groups, imgs_per_part=body.imgs_per_part,
                          seed=body.seed)
    summary = build_index(state.settings, train=True, epochs=body.epochs)
    n = _sync_parts_from_metadata(state)
    state.rebuild_engine()
    return {"dataset": ds, "index": summary, "parts_synced": n, "ready": state.ready}


@router.get("/sample-image")
def sample_image(part_no: str, seed: int = 0, state: AppState = Depends(get_state)):
    """指定品番のホールドアウト撮影画像（PNG）を生成して返す（デモ用）。

    索引に登録された画像とは別シードで描画するため、現実的な「新規撮影」を再現する。
    """
    cfg_path = _gen_config_path(state)
    if not cfg_path.exists():
        raise HTTPException(404, "生成設定がありません（合成デモデータ未生成）。")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    specs = generate_part_specs(cfg["n_parts"], cfg["n_groups"], cfg["seed"])
    spec = next((s for s in specs if s.part_no == part_no), None)
    if spec is None:
        raise HTTPException(404, f"品番 {part_no} が見つかりません。")
    # seed=0 は「ランダムな新規撮影」、それ以外は再現可能
    render_seed = None if seed == 0 else seed
    img = render_part(spec, seed=render_seed, jitter=True)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return Response(content=buf.getvalue(), media_type="image/png")
