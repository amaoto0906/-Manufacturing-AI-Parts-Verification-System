"""Embedder: バックボーン + 投影ヘッドを束ねた埋め込み生成器。

照合に使う最終埋め込み（L2正規化済み）を一手に提供する。投影ヘッドが
学習済みであれば適用し、無ければバックボーン埋め込みをそのまま正規化して返す。
"""
from __future__ import annotations

from typing import Sequence

import numpy as np
from PIL import Image

from .backbones import get_backbone
from .metric_learning.head import apply_projection_np, load_projection_np


class Embedder:
    def __init__(self, settings):
        self.settings = settings
        self.backbone = get_backbone(settings)
        self.proj = load_projection_np(settings.projection_path) if settings.use_projection else None

    @property
    def dim(self) -> int:
        return self.proj.out_dim if self.proj is not None else self.backbone.dim

    @property
    def info(self) -> dict:
        return {
            "backbone": self.backbone.name,
            "backbone_dim": self.backbone.dim,
            "projection": self.proj is not None,
            "dim": self.dim,
        }

    def reload_projection(self) -> None:
        """学習直後などに投影ヘッドを再読み込みする。"""
        self.proj = (
            load_projection_np(self.settings.projection_path)
            if self.settings.use_projection else None
        )

    def embed(self, images: Sequence[Image.Image]) -> np.ndarray:
        base = self.backbone.embed(images)
        return apply_projection_np(base, self.proj)

    def embed_one(self, image: Image.Image) -> np.ndarray:
        return self.embed([image])[0]
