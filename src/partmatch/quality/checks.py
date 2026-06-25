"""撮影画像の品質ゲート。

AI 照合の前に画像が「判定に使える品質か」を検査し、ダメな場合は照合せず
RETAKE（再撮影）を促す。これにより、ピンボケ・露出不良・反射・位置ズレ・
部品不在といった撮影起因の誤判定を未然に防ぐ。numpy + PIL のみで動作。

検査項目:
    blur        : 鮮鋭度（ラプラシアン分散）。低い→ピンボケ
    exposure    : 平均輝度・白飛び・黒つぶれ比率
    contrast    : 標準偏差（低い→のっぺり/無地）
    glare       : 鏡面反射（高輝度クラスタ）比率。金属部品で重要
    coverage    : 前景（部品）面積比。小さすぎ→不在 / 大きすぎ→寄りすぎ
    centering   : 部品重心の中心からのズレ
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np
from PIL import Image

from ..preprocess import center_square


@dataclass
class QualityReport:
    ok: bool
    action: str                     # "pass" | "retake"
    issues: List[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "action": self.action,
            "issues": self.issues,
            "metrics": {k: round(float(v), 4) for k, v in self.metrics.items()},
        }


# 既定しきい値（現場の実画像で必ず再キャリブレーションすること）
# blur_min は被写体のテクスチャ量に依存する。実写は合成形状より高い値になる。
DEFAULTS = dict(
    blur_min=0.0004,        # ラプラシアン分散（[0,1]正規化画像）
    bright_min=0.12,
    bright_max=0.92,
    clip_high_max=0.18,     # 白飛び画素比率の上限
    clip_low_max=0.30,      # 黒つぶれ画素比率の上限
    contrast_min=0.045,
    glare_max=0.06,         # 鏡面反射比率の上限
    coverage_min=0.04,      # 前景面積比の下限（部品不在検出）
    coverage_max=0.97,      # 前景面積比の上限（寄りすぎ）
    center_offset_max=0.28,  # 中心ズレ（画像サイズ比）
)


def _laplacian_var(a: np.ndarray) -> float:
    """ラプラシアンフィルタ応答の分散（鮮鋭度）。"""
    lap = (
        -4 * a
        + np.roll(a, 1, 0) + np.roll(a, -1, 0)
        + np.roll(a, 1, 1) + np.roll(a, -1, 1)
    )[1:-1, 1:-1]
    return float(lap.var())


def assess_quality(img: Image.Image, **overrides) -> QualityReport:
    """画像品質を評価し QualityReport を返す。"""
    cfg = {**DEFAULTS, **overrides}
    g = center_square(img).convert("L").resize((256, 256), Image.BILINEAR)
    a = np.asarray(g, dtype=np.float32) / 255.0

    issues: List[str] = []
    metrics: dict = {}

    # --- 鮮鋭度 ---
    blur = _laplacian_var(a)
    metrics["blur"] = blur
    if blur < cfg["blur_min"]:
        issues.append("ピンボケ（鮮鋭度不足）")

    # --- 露出 ---
    mean = float(a.mean())
    clip_high = float((a > 0.96).mean())
    clip_low = float((a < 0.04).mean())
    metrics.update(brightness=mean, clip_high=clip_high, clip_low=clip_low)
    if mean < cfg["bright_min"]:
        issues.append("露出不足（暗すぎ）")
    if mean > cfg["bright_max"]:
        issues.append("露出過多（明るすぎ）")
    if clip_high > cfg["clip_high_max"]:
        issues.append("白飛び")
    if clip_low > cfg["clip_low_max"]:
        issues.append("黒つぶれ")

    # --- コントラスト ---
    contrast = float(a.std())
    metrics["contrast"] = contrast
    if contrast < cfg["contrast_min"]:
        issues.append("コントラスト不足（無地/背景のみの可能性）")

    # --- 鏡面反射（グレア）: 高輝度の連続クラスタ ---
    glare = float((a > 0.98).mean())
    metrics["glare"] = glare
    if glare > cfg["glare_max"]:
        issues.append("鏡面反射（金属反射）が強い")

    # --- 前景被覆率・中心ズレ（Otsu 風二値化） ---
    thr = float(np.clip(a.mean() - 0.5 * a.std(), 0.05, 0.95))
    fg = a < thr if a.mean() > 0.5 else a > thr  # 背景の明暗に両対応
    coverage = float(fg.mean())
    metrics["coverage"] = coverage
    if coverage < cfg["coverage_min"]:
        issues.append("部品が写っていない/小さすぎる")
    elif coverage > cfg["coverage_max"]:
        issues.append("部品が大きすぎる（寄りすぎ/見切れ）")

    if fg.any():
        ys, xs = np.nonzero(fg)
        cy, cx = ys.mean() / a.shape[0], xs.mean() / a.shape[1]
        offset = float(np.hypot(cy - 0.5, cx - 0.5))
        metrics["center_offset"] = offset
        if offset > cfg["center_offset_max"]:
            issues.append("部品の位置ズレ（中心から外れている）")

    ok = len(issues) == 0
    return QualityReport(ok=ok, action="pass" if ok else "retake",
                         issues=issues, metrics=metrics)
