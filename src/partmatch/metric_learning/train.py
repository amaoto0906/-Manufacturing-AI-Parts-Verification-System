"""投影ヘッドの学習。

キャッシュ済みバックボーン埋め込み（numpy）に対し、ArcFace 損失で投影ヘッドを
学習する。バックボーンは凍結扱いのため CPU でも数秒で収束する。学習後、重みを
npz にエクスポートし、推論は純 numpy で実行できる。
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Sequence

import numpy as np

from .head import make_torch_head
from .losses import make_arcface


def train_projection(
    embeddings: np.ndarray,
    labels: Sequence[str],
    out_path,
    out_dim: int = 256,
    hidden: int = 512,
    epochs: int = 60,
    batch_size: int = 64,
    lr: float = 1e-3,
    arc_s: float = 30.0,
    arc_m: float = 0.30,
    seed: int = 0,
    verbose: bool = False,
) -> dict:
    """投影ヘッドを学習し npz を out_path に保存。学習指標 dict を返す。"""
    import torch

    torch.manual_seed(seed)
    embeddings = np.asarray(embeddings, dtype=np.float32)
    classes: List[str] = sorted(set(labels))
    cls_to_idx = {c: i for i, c in enumerate(classes)}
    y = np.array([cls_to_idx[l] for l in labels], dtype=np.int64)
    n, in_dim = embeddings.shape
    n_classes = len(classes)

    # BatchNorm 安定化のため hidden をデータ規模に合わせて抑制
    hidden = min(hidden, max(64, in_dim))
    out_dim = min(out_dim, in_dim)

    head = make_torch_head(in_dim, hidden, out_dim)
    arc = make_arcface(out_dim, n_classes, s=arc_s, m=arc_m)
    params = list(head.parameters()) + list(arc.parameters())
    opt = torch.optim.Adam(params, lr=lr, weight_decay=1e-4)

    X = torch.from_numpy(embeddings)
    Y = torch.from_numpy(y)
    rng = np.random.default_rng(seed)

    head.train()
    arc.train()
    last = {"loss": float("nan"), "acc": 0.0}
    for ep in range(epochs):
        perm = rng.permutation(n)
        tot_loss = 0.0
        correct = 0
        for s0 in range(0, n, batch_size):
            bidx = perm[s0:s0 + batch_size]
            if len(bidx) < 2:  # BatchNorm 用に最低2件
                continue
            xb = X[bidx]
            yb = Y[bidx]
            opt.zero_grad()
            emb = head(xb)
            loss, cos = arc(emb, yb)
            loss.backward()
            opt.step()
            tot_loss += float(loss) * len(bidx)
            correct += int((cos.argmax(1) == yb).sum())
        last = {"loss": tot_loss / n, "acc": correct / n}
        if verbose and (ep % 10 == 0 or ep == epochs - 1):
            print(f"epoch {ep:3d}  loss={last['loss']:.4f}  train_acc={last['acc']:.4f}")

    head.eval()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # np.savez は拡張子 .npz を付与するため、設定パスと一致させる
    tmp = out_path.with_suffix("")
    head.export_npz(str(tmp))
    if not out_path.exists() and tmp.with_suffix(".npz").exists():
        tmp.with_suffix(".npz").replace(out_path)

    return {
        "in_dim": in_dim,
        "out_dim": out_dim,
        "n_classes": n_classes,
        "n_samples": n,
        "final_loss": last["loss"],
        "train_acc": last["acc"],
        "out_path": str(out_path),
    }
