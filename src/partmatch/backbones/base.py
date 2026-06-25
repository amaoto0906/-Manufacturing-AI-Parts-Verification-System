"""特徴抽出バックボーンの抽象基底。

すべてのバックボーンは PIL 画像のリストを受け取り、L2 正規化済みの
float32 埋め込み (N, D) を返す。これにより classic / torchvision / dinov2 を
完全に差し替え可能（pluggable）にし、PoC から本番への移行を容易にする。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

import numpy as np
from PIL import Image


def l2_normalize(x: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    """行ごとに L2 正規化する。コサイン類似度 = 内積 とするための前処理。"""
    x = np.asarray(x, dtype=np.float32)
    if x.ndim == 1:
        x = x[None, :]
    norm = np.linalg.norm(x, axis=1, keepdims=True)
    return x / np.maximum(norm, eps)


class EmbeddingBackend(ABC):
    """埋め込み抽出器の共通インタフェース。"""

    name: str = "base"

    @property
    @abstractmethod
    def dim(self) -> int:
        """出力埋め込み次元数。"""

    @abstractmethod
    def _embed_raw(self, images: Sequence[Image.Image]) -> np.ndarray:
        """正規化前の生埋め込み (N, D) を返す。サブクラスが実装する。"""

    def embed(self, images: Sequence[Image.Image]) -> np.ndarray:
        """L2 正規化済み埋め込み (N, D) float32 を返す。"""
        if not images:
            return np.zeros((0, self.dim), dtype=np.float32)
        raw = self._embed_raw(images)
        return l2_normalize(raw)

    def embed_one(self, image: Image.Image) -> np.ndarray:
        """単一画像の埋め込み (D,) を返す。"""
        return self.embed([image])[0]
