"""dinov2 バックボーン（本番推奨）: 基盤モデル DINOv2 の自己教師ありViT特徴。

torch.hub 経由で facebookresearch/dinov2 をロードする。CLS トークン埋め込みは
ラベルなしで学習された汎用視覚特徴であり、類似部品の照合に対して classic より
高い表現力を持つ。GPU 推奨だが CPU でも ViT-S なら動作する。

  arch 例: dinov2_vits14 (384d) / dinov2_vitb14 (768d) / dinov2_vitl14 (1024d)

初回ロードでモデル定義と重みがダウンロードされる（インターネット必要）。
"""
from __future__ import annotations

from typing import Sequence

import numpy as np
from PIL import Image

from .base import EmbeddingBackend
from ..preprocess import prepare

_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class DinoV2Backend(EmbeddingBackend):
    name = "dinov2"

    def __init__(self, arch: str = "dinov2_vits14", device: str = "cpu",
                 image_size: int = 224) -> None:
        import torch

        self._torch = torch
        self.device = device
        # ViT/14 はパッチ14。入力辺は14の倍数にする
        self.image_size = (image_size // 14) * 14
        self.model = torch.hub.load("facebookresearch/dinov2", arch)
        self.model.eval().to(device)
        self._dim = int(self.model.embed_dim)

    @property
    def dim(self) -> int:
        return self._dim

    def _to_tensor(self, images: Sequence[Image.Image]):
        arrs = []
        for im in images:
            p = prepare(im, self.image_size)
            a = np.asarray(p, dtype=np.float32) / 255.0
            a = (a - _IMAGENET_MEAN) / _IMAGENET_STD
            arrs.append(a.transpose(2, 0, 1))
        batch = np.stack(arrs).astype(np.float32)
        return self._torch.from_numpy(batch).to(self.device)

    def _embed_raw(self, images: Sequence[Image.Image]) -> np.ndarray:
        torch = self._torch
        with torch.no_grad():
            feats = self.model(self._to_tensor(images))  # CLS 埋め込み (N, dim)
        return feats.cpu().numpy().astype(np.float32)
