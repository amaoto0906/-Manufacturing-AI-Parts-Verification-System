"""バックボーンのファクトリ。"""
from __future__ import annotations

from functools import lru_cache

from .base import EmbeddingBackend, l2_normalize
from .classic import ClassicBackend

__all__ = ["EmbeddingBackend", "l2_normalize", "get_backbone", "build_backbone"]


def build_backbone(backend: str, *, torchvision_arch: str = "mobilenet_v3_small",
                   dinov2_arch: str = "dinov2_vits14", device: str = "cpu",
                   image_size: int = 224) -> EmbeddingBackend:
    """指定されたバックエンド名からバックボーンを生成する。"""
    backend = backend.lower()
    if backend == "classic":
        return ClassicBackend()
    if backend == "torchvision":
        from .torchvision_backbone import TorchvisionBackend
        return TorchvisionBackend(torchvision_arch, device, image_size)
    if backend == "dinov2":
        from .dinov2 import DinoV2Backend
        return DinoV2Backend(dinov2_arch, device, image_size)
    raise ValueError(f"未知のバックエンド: {backend}")


@lru_cache(maxsize=4)
def _cached(backend, torchvision_arch, dinov2_arch, device, image_size):
    return build_backbone(
        backend, torchvision_arch=torchvision_arch, dinov2_arch=dinov2_arch,
        device=device, image_size=image_size,
    )


def get_backbone(settings) -> EmbeddingBackend:
    """設定に基づきキャッシュされたバックボーンを返す。"""
    return _cached(
        settings.backend, settings.torchvision_arch, settings.dinov2_arch,
        settings.device, settings.image_size,
    )
