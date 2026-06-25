"""ベクトル検索ストア（Faiss + numpy フォールバック）。

L2 正規化済みベクトルに対し内積（= コサイン類似度）で Top-K 検索する。
Faiss が使えれば高速な IndexFlatIP を使用し、無ければ numpy で同等の結果を返す。
本番では 2万品番 × 複数枚 = 数十万ベクトルでも 1秒以内を狙える。大規模化時は
IndexIVFFlat / IndexHNSWFlat へ差し替え可能な設計。

各ベクトルには行メタデータ（part_no, image_id 等）を紐付けて保持する。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np

try:
    import faiss  # type: ignore
    _HAS_FAISS = True
except Exception:  # pragma: no cover
    _HAS_FAISS = False


@dataclass
class SearchHit:
    row: int
    score: float
    meta: dict


class VectorStore:
    """埋め込みベクトルとメタデータを保持し Top-K 検索を提供する。"""

    def __init__(self, dim: int):
        self.dim = int(dim)
        self.vectors = np.zeros((0, dim), dtype=np.float32)
        self.meta: List[dict] = []
        self._index = None
        self._dirty = True

    # --- 構築 ---
    def add(self, vectors: np.ndarray, metas: List[dict]) -> None:
        vectors = np.ascontiguousarray(vectors, dtype=np.float32)
        if vectors.ndim == 1:
            vectors = vectors[None, :]
        assert vectors.shape[1] == self.dim, "次元不一致"
        assert vectors.shape[0] == len(metas), "ベクトル数とメタ数が不一致"
        self.vectors = np.vstack([self.vectors, vectors]) if self.vectors.size else vectors
        self.meta.extend(metas)
        self._dirty = True

    def _build(self) -> None:
        if _HAS_FAISS and len(self.vectors):
            idx = faiss.IndexFlatIP(self.dim)
            idx.add(self.vectors)
            self._index = idx
        else:
            self._index = None
        self._dirty = False

    # --- 検索 ---
    def search(self, query: np.ndarray, k: int = 5) -> List[SearchHit]:
        if len(self.vectors) == 0:
            return []
        if self._dirty:
            self._build()
        q = np.ascontiguousarray(query, dtype=np.float32).reshape(1, -1)
        k = min(k, len(self.vectors))
        if self._index is not None:
            scores, idxs = self._index.search(q, k)
            scores, idxs = scores[0], idxs[0]
        else:  # numpy フォールバック
            sims = (self.vectors @ q[0])
            idxs = np.argsort(-sims)[:k]
            scores = sims[idxs]
        return [SearchHit(int(i), float(s), self.meta[int(i)])
                for i, s in zip(idxs, scores) if i >= 0]

    # --- 永続化 ---
    def save(self, path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.save(path.with_suffix(".vectors.npy"), self.vectors)
        with path.with_suffix(".meta.json").open("w", encoding="utf-8") as f:
            json.dump({"dim": self.dim, "meta": self.meta}, f, ensure_ascii=False)

    @classmethod
    def load(cls, path) -> "VectorStore":
        path = Path(path)
        with path.with_suffix(".meta.json").open(encoding="utf-8") as f:
            payload = json.load(f)
        store = cls(payload["dim"])
        vec_path = path.with_suffix(".vectors.npy")
        if vec_path.exists():
            store.vectors = np.load(vec_path).astype(np.float32)
        store.meta = payload["meta"]
        store._dirty = True
        return store

    @property
    def size(self) -> int:
        return len(self.vectors)

    @property
    def backend(self) -> str:
        return "faiss" if _HAS_FAISS else "numpy"
