"""classic バックボーン: numpy + PIL のみで動作する手作り特徴記述子。

GPU・追加DL・重い依存を一切必要とせず、どの環境でも確実に動く。
金属プレス部品の識別に効く以下の特徴を結合した、形状重視の記述子:

  1. HOG-lite  : Sobel 勾配の方向ヒストグラム（エッジ・輪郭の向き）
  2. Hu モーメント : シルエットの回転・スケール不変な形状記述
  3. 強度グリッド : 12x12 ブロック平均（明暗パターン）
  4. 半径プロファイル : 重心からの放射状強度（穴・外形の分布）

各特徴グループを個別に L2 正規化してから結合することで、特定グループの
スケールが支配しないように調整している。本番では DINOv2 を推奨するが、
本記述子は堅牢なフォールバック兼ベースラインとして機能する。
"""
from __future__ import annotations

from typing import Sequence

import numpy as np
from PIL import Image

from .base import EmbeddingBackend
from ..preprocess import to_gray_array

_SIZE = 160
_HOG_CELLS = 6      # 6x6 セル
_HOG_BINS = 9       # 0..180 度を 9 分割
_GRID = 12          # 12x12 強度グリッド
_RADIAL_BINS = 32   # 半径方向 32 ビン


def _otsu_mask(a: np.ndarray) -> np.ndarray:
    """Otsu 法で前景マスク（部品=True）を求める。背景は明・暗どちらでも対応。"""
    hist, _ = np.histogram(a, bins=256, range=(0.0, 1.0))
    total = a.size
    sum_all = np.dot(np.arange(256), hist)
    w_b = 0.0
    sum_b = 0.0
    max_var = -1.0
    thr = 128
    for t in range(256):
        w_b += hist[t]
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += t * hist[t]
        m_b = sum_b / w_b
        m_f = (sum_all - sum_b) / w_f
        var = w_b * w_f * (m_b - m_f) ** 2
        if var > max_var:
            max_var = var
            thr = t
    thr_val = thr / 255.0
    # 前景は背景より画素数が少ない側と仮定し、少数派をマスクにする
    high = a >= thr_val
    return high if high.mean() <= 0.5 else ~high


def _hog_lite(a: np.ndarray) -> np.ndarray:
    """Sobel 勾配による方向ヒストグラム（HOG-lite）。"""
    gx = np.zeros_like(a)
    gy = np.zeros_like(a)
    gx[:, 1:-1] = a[:, 2:] - a[:, :-2]
    gy[1:-1, :] = a[2:, :] - a[:-2, :]
    mag = np.sqrt(gx * gx + gy * gy)
    ang = (np.arctan2(gy, gx) % np.pi)  # 0..pi（無向エッジ）
    bin_idx = np.minimum((ang / np.pi * _HOG_BINS).astype(int), _HOG_BINS - 1)

    h, w = a.shape
    ch, cw = h // _HOG_CELLS, w // _HOG_CELLS
    feats = []
    for i in range(_HOG_CELLS):
        for j in range(_HOG_CELLS):
            mb = mag[i * ch:(i + 1) * ch, j * cw:(j + 1) * cw]
            bb = bin_idx[i * ch:(i + 1) * ch, j * cw:(j + 1) * cw]
            hist = np.bincount(bb.ravel(), weights=mb.ravel(), minlength=_HOG_BINS)
            feats.append(hist)
    v = np.concatenate(feats).astype(np.float32)
    return v


def _hu_moments(mask: np.ndarray) -> np.ndarray:
    """シルエットの Hu モーメント（7次元・対数スケール）。"""
    ys, xs = np.nonzero(mask)
    if xs.size == 0:
        return np.zeros(7, dtype=np.float32)
    x = xs.astype(np.float64)
    y = ys.astype(np.float64)
    m00 = float(mask.sum())
    xbar = x.mean()
    ybar = y.mean()

    def mu(p, q):
        return np.sum(((x - xbar) ** p) * ((y - ybar) ** q))

    def nu(p, q):
        return mu(p, q) / (m00 ** (1 + (p + q) / 2.0) + 1e-12)

    n20, n02, n11 = nu(2, 0), nu(0, 2), nu(1, 1)
    n30, n12, n21, n03 = nu(3, 0), nu(1, 2), nu(2, 1), nu(0, 3)

    h = np.zeros(7, dtype=np.float64)
    h[0] = n20 + n02
    h[1] = (n20 - n02) ** 2 + 4 * n11 ** 2
    h[2] = (n30 - 3 * n12) ** 2 + (3 * n21 - n03) ** 2
    h[3] = (n30 + n12) ** 2 + (n21 + n03) ** 2
    h[4] = (n30 - 3 * n12) * (n30 + n12) * ((n30 + n12) ** 2 - 3 * (n21 + n03) ** 2) \
        + (3 * n21 - n03) * (n21 + n03) * (3 * (n30 + n12) ** 2 - (n21 + n03) ** 2)
    h[5] = (n20 - n02) * ((n30 + n12) ** 2 - (n21 + n03) ** 2) \
        + 4 * n11 * (n30 + n12) * (n21 + n03)
    h[6] = (3 * n21 - n03) * (n30 + n12) * ((n30 + n12) ** 2 - 3 * (n21 + n03) ** 2) \
        - (n30 - 3 * n12) * (n21 + n03) * (3 * (n30 + n12) ** 2 - (n21 + n03) ** 2)
    # 対数スケール（符号保持）
    return (-np.sign(h) * np.log10(np.abs(h) + 1e-12)).astype(np.float32)


def _intensity_grid(a: np.ndarray) -> np.ndarray:
    """12x12 ブロック平均強度。"""
    h, w = a.shape
    ch, cw = h // _GRID, w // _GRID
    out = a[:ch * _GRID, :cw * _GRID].reshape(_GRID, ch, _GRID, cw).mean(axis=(1, 3))
    return out.ravel().astype(np.float32)


def _radial_profile(mask: np.ndarray) -> np.ndarray:
    """重心からの放射状の前景密度プロファイル。"""
    h, w = mask.shape
    ys, xs = np.nonzero(mask)
    if xs.size == 0:
        return np.zeros(_RADIAL_BINS, dtype=np.float32)
    cy, cx = ys.mean(), xs.mean()
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    rmax = r.max() + 1e-6
    bins = np.minimum((r / rmax * _RADIAL_BINS).astype(int), _RADIAL_BINS - 1)
    fg = np.bincount(bins[mask].ravel(), minlength=_RADIAL_BINS).astype(np.float32)
    tot = np.bincount(bins.ravel(), minlength=_RADIAL_BINS).astype(np.float32)
    return fg / np.maximum(tot, 1.0)


def _group_norm(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 1e-8 else v


def descriptor(img: Image.Image) -> np.ndarray:
    """単一画像の手作り記述子を返す。"""
    a = to_gray_array(img, _SIZE)
    mask = _otsu_mask(a)
    parts = [
        _group_norm(_hog_lite(a)),
        _group_norm(_hu_moments(mask)),
        _group_norm(_intensity_grid(a)),
        _group_norm(_radial_profile(mask)),
    ]
    return np.concatenate(parts).astype(np.float32)


class ClassicBackend(EmbeddingBackend):
    """手作り記述子バックボーン。"""

    name = "classic"

    def __init__(self) -> None:
        # 次元数は構成から決まる
        self._dim = (
            _HOG_CELLS * _HOG_CELLS * _HOG_BINS + 7 + _GRID * _GRID + _RADIAL_BINS
        )

    @property
    def dim(self) -> int:
        return self._dim

    def _embed_raw(self, images: Sequence[Image.Image]) -> np.ndarray:
        return np.stack([descriptor(im) for im in images]).astype(np.float32)
