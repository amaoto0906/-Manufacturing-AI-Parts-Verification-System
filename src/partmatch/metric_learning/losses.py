"""ArcFace 損失（加法的角度マージン）。

L2 正規化済み埋め込みと、クラス（品番）プロトタイプの間の角度に対し、
正解クラスへ角度マージン m を加えることで、クラス内をより密に、クラス間を
より離す。類似部品の識別境界を鋭くするのに有効。

学習時のみクラス分類器を使い、推論では使わない（新規品番はギャラリ追加で対応）。
"""
from __future__ import annotations


def make_arcface(dim: int, n_classes: int, s: float = 30.0, m: float = 0.30):
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    class ArcFace(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.weight = nn.Parameter(torch.randn(n_classes, dim) * 0.01)
            self.s = s
            self.m = m

        def forward(self, emb, labels):
            # emb は L2 正規化済み前提
            w = F.normalize(self.weight, dim=1)
            cos = torch.clamp(emb @ w.t(), -1 + 1e-6, 1 - 1e-6)
            theta = torch.acos(cos)
            target = F.one_hot(labels, cos.size(1)).float()
            marg = torch.cos(theta + self.m * target)
            logits = self.s * marg
            return F.cross_entropy(logits, labels), cos

    return ArcFace()
