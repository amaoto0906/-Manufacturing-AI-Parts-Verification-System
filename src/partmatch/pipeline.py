"""データ収集 → 埋め込み → 距離学習 → 索引構築 の一気通貫パイプライン。

バックボーンのベース埋め込みを一度だけ計算してキャッシュし、(1) 投影ヘッドの
学習と (2) 索引登録の双方で再利用する。これにより重い特徴抽出を二度実行しない。
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from .backbones import get_backbone
from .index.store import VectorStore
from .metric_learning.head import apply_projection_np, load_projection_np
from .preprocess import load_image

IMG_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def collect_images(raw_dir) -> List[Tuple[str, str]]:
    """raw/<part_no>/*.png を走査し (part_no, path) のリストを返す。"""
    raw = Path(raw_dir)
    items: List[Tuple[str, str]] = []
    for pdir in sorted(p for p in raw.iterdir() if p.is_dir()):
        for img in sorted(pdir.iterdir()):
            if img.suffix.lower() in IMG_EXT:
                items.append((pdir.name, str(img)))
    return items


def load_parts_meta(metadata_dir) -> Dict[str, dict]:
    """parts.csv を読み込み part_no -> メタ情報の辞書を返す。"""
    path = Path(metadata_dir) / "parts.csv"
    meta: Dict[str, dict] = {}
    if not path.exists():
        return meta
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            gid = row.get("group_id")
            meta[row["part_no"]] = {
                "group_id": int(gid) if gid not in (None, "") else None,
                "shape": row.get("shape"),
            }
    return meta


def compute_base_embeddings(backbone, items, batch_size: int = 32):
    """バックボーンのベース埋め込みを計算する。"""
    labels = [pn for pn, _ in items]
    paths = [p for _, p in items]
    vecs = []
    for s0 in range(0, len(items), batch_size):
        imgs = [load_image(p) for p in paths[s0:s0 + batch_size]]
        vecs.append(backbone.embed(imgs))
    base = np.vstack(vecs) if vecs else np.zeros((0, backbone.dim), dtype=np.float32)
    return base, labels, paths


def build_index(
    settings,
    raw_dir=None,
    metadata_dir=None,
    train: bool = True,
    epochs: int = 60,
    verbose: bool = False,
) -> dict:
    """データセットから索引（VectorStore）を構築して保存する。"""
    raw_dir = Path(raw_dir) if raw_dir else settings.data_dir / "raw"
    metadata_dir = Path(metadata_dir) if metadata_dir else settings.data_dir / "metadata"

    backbone = get_backbone(settings)
    items = collect_images(raw_dir)
    if not items:
        raise RuntimeError(f"画像が見つかりません: {raw_dir}")

    base, labels, paths = compute_base_embeddings(backbone, items)
    parts_meta = load_parts_meta(metadata_dir)

    train_summary = None
    proj = None
    if train and settings.use_projection:
        from .metric_learning.train import train_projection
        train_summary = train_projection(
            base, labels, settings.projection_path,
            out_dim=settings.projection_dim, epochs=epochs, verbose=verbose,
        )
        proj = load_projection_np(settings.projection_path)
    elif settings.use_projection:
        proj = load_projection_np(settings.projection_path)

    final = apply_projection_np(base, proj)
    store = VectorStore(final.shape[1])
    metas = [
        {"part_no": pn, "group_id": parts_meta.get(pn, {}).get("group_id"),
         "image_path": path}
        for pn, path in zip(labels, paths)
    ]
    store.add(final, metas)
    store.save(settings.index_path)

    return {
        "n_images": len(items),
        "n_parts": len(set(labels)),
        "dim": final.shape[1],
        "backend": store.backend,
        "trained": train_summary is not None,
        "train_summary": train_summary,
        "index_path": str(settings.index_path),
    }


def load_store(settings) -> Optional[VectorStore]:
    """保存済み索引をロードする。無ければ None。"""
    meta_path = Path(str(settings.index_path)).with_suffix(".meta.json")
    if not meta_path.exists():
        return None
    return VectorStore.load(settings.index_path)
