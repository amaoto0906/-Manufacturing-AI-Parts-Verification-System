"""距離学習（Metric Learning）パイプライン。"""
from .head import apply_projection_np, load_projection_np

__all__ = ["apply_projection_np", "load_projection_np", "train_projection"]


def train_projection(*args, **kwargs):
    # torch を必要とするため遅延 import
    from .train import train_projection as _t
    return _t(*args, **kwargs)
