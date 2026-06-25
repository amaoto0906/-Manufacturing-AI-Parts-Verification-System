"""投影ヘッド（Projection Head）。

バックボーン埋め込みを、照合に適した距離空間へ写像する小さな MLP。
学習は torch（losses.py の ArcFace と併用）だが、**推論は純 numpy** で行えるよう
重みを npz にエクスポートできる。これにより classic 経路は推論時に torch 不要。

  forward:  x -> Linear -> BatchNorm -> ReLU -> Linear -> L2正規化
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np

from ..backbones.base import l2_normalize


def make_torch_head(in_dim: int, hidden: int, out_dim: int):
    """学習用の torch ProjectionHead を生成する（torch を遅延 import）。"""
    import torch
    import torch.nn as nn

    class ProjectionHead(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.fc1 = nn.Linear(in_dim, hidden)
            self.bn = nn.BatchNorm1d(hidden)
            self.act = nn.ReLU(inplace=True)
            self.fc2 = nn.Linear(hidden, out_dim)

        def forward(self, x):
            h = self.act(self.bn(self.fc1(x)))
            o = self.fc2(h)
            return torch.nn.functional.normalize(o, dim=1)

        def export_npz(self, path) -> None:
            sd = self.state_dict()
            np.savez(
                path,
                in_dim=in_dim, hidden=hidden, out_dim=out_dim,
                w1=sd["fc1.weight"].cpu().numpy(), b1=sd["fc1.bias"].cpu().numpy(),
                bn_w=sd["bn.weight"].cpu().numpy(), bn_b=sd["bn.bias"].cpu().numpy(),
                bn_rm=sd["bn.running_mean"].cpu().numpy(),
                bn_rv=sd["bn.running_var"].cpu().numpy(),
                bn_eps=np.float32(self.bn.eps),
                w2=sd["fc2.weight"].cpu().numpy(), b2=sd["fc2.bias"].cpu().numpy(),
            )

    return ProjectionHead()


# ---- 純 numpy 推論 ----
class NumpyProjection:
    """npz からロードした投影ヘッドを numpy のみで適用する。"""

    def __init__(self, p: dict):
        self.w1, self.b1 = p["w1"], p["b1"]
        self.bn_w, self.bn_b = p["bn_w"], p["bn_b"]
        self.bn_rm, self.bn_rv = p["bn_rm"], p["bn_rv"]
        self.bn_eps = float(p["bn_eps"])
        self.w2, self.b2 = p["w2"], p["b2"]
        self.out_dim = int(p["out_dim"])

    def __call__(self, x: np.ndarray) -> np.ndarray:
        x = np.atleast_2d(np.asarray(x, dtype=np.float32))
        h = x @ self.w1.T + self.b1
        h = (h - self.bn_rm) / np.sqrt(self.bn_rv + self.bn_eps) * self.bn_w + self.bn_b
        h = np.maximum(h, 0.0)              # ReLU
        o = h @ self.w2.T + self.b2
        return l2_normalize(o)


def load_projection_np(path) -> Optional[NumpyProjection]:
    """npz から numpy 投影ヘッドをロードする。無ければ None。"""
    path = Path(path)
    if not path.exists():
        return None
    data = np.load(path)
    return NumpyProjection({k: data[k] for k in data.files})


def apply_projection_np(x: np.ndarray, proj: Optional[NumpyProjection]) -> np.ndarray:
    """投影ヘッドがあれば適用、無ければ L2 正規化のみ。"""
    if proj is None:
        return l2_normalize(x)
    return proj(x)
