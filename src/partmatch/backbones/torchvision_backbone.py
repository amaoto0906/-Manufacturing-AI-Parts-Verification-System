"""torchvision バックボーン: ImageNet 事前学習 CNN を汎用特徴抽出器として使う。

mobilenet_v3_small（軽量）/ resnet18 などの最終分類層を除去し、
プール済み特徴ベクトルを埋め込みとして取り出す。CPU でも動作する。
重みは初回に自動ダウンロードされる（インターネット必要）。
"""
from __future__ import annotations

from typing import Sequence

import numpy as np
from PIL import Image

from .base import EmbeddingBackend
from ..preprocess import prepare

_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class TorchvisionBackend(EmbeddingBackend):
    name = "torchvision"

    def __init__(self, arch: str = "mobilenet_v3_small", device: str = "cpu",
                 image_size: int = 224) -> None:
        import torch
        import torchvision

        self._torch = torch
        self.device = device
        self.image_size = image_size
        self.arch = arch

        weights_enum = {
            "mobilenet_v3_small": "MobileNet_V3_Small_Weights",
            "resnet18": "ResNet18_Weights",
            "resnet50": "ResNet50_Weights",
        }.get(arch)
        ctor = getattr(torchvision.models, arch)
        weights = getattr(torchvision.models, weights_enum).DEFAULT if weights_enum else None
        model = ctor(weights=weights)

        # 分類層を Identity に置き換えてプール済み特徴を取り出す
        if hasattr(model, "fc"):           # resnet 系
            self._dim = model.fc.in_features
            model.fc = torch.nn.Identity()
        elif hasattr(model, "classifier"):  # mobilenet / efficientnet 系
            cls = model.classifier
            first = cls[0] if isinstance(cls, torch.nn.Sequential) else cls
            self._dim = first.in_features
            model.classifier = torch.nn.Identity()
        else:
            raise ValueError(f"未対応のアーキテクチャ: {arch}")

        model.eval().to(device)
        self.model = model

    @property
    def dim(self) -> int:
        return self._dim

    def _to_tensor(self, images: Sequence[Image.Image]):
        arrs = []
        for im in images:
            p = prepare(im, self.image_size)
            a = np.asarray(p, dtype=np.float32) / 255.0
            a = (a - _IMAGENET_MEAN) / _IMAGENET_STD
            arrs.append(a.transpose(2, 0, 1))  # HWC -> CHW
        batch = np.stack(arrs).astype(np.float32)
        return self._torch.from_numpy(batch).to(self.device)

    def _embed_raw(self, images: Sequence[Image.Image]) -> np.ndarray:
        torch = self._torch
        with torch.no_grad():
            feats = self.model(self._to_tensor(images))
            if feats.ndim > 2:
                feats = torch.flatten(feats, 1)
        return feats.cpu().numpy().astype(np.float32)
