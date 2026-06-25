"""画質ゲートしきい値の自動キャリブレーション。

現場の実画像（既知の良品撮影）の各メトリクス分布から、ほとんどの良品が通過する
しきい値を自動導出する。不良画像が用意できれば、それらが正しく弾かれるか（分離度）
も併せて検証する。

標準的な手順:
  1) 良品画像で assess_quality を実行し、各メトリクスの分布を取得
  2) 下限系(min)はパーセンタイル下側、上限系(max)はパーセンタイル上側にマージンを付与
  3) 不良画像があれば棄却率を算出し、しきい値の妥当性を報告

これにより `quality/checks.py: DEFAULTS` を**現場データに合わせて置き換え**られる。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np
from PIL import Image

from ..preprocess import load_image
from .checks import DEFAULTS, assess_quality

# メトリクス名 → (方向, DEFAULTSのキー)
METRIC_SPEC = {
    "blur": ("min", "blur_min"),
    "brightness": ("range", ("bright_min", "bright_max")),
    "clip_high": ("max", "clip_high_max"),
    "clip_low": ("max", "clip_low_max"),
    "contrast": ("min", "contrast_min"),
    "glare": ("max", "glare_max"),
    "coverage": ("range", ("coverage_min", "coverage_max")),
    "center_offset": ("max", "center_offset_max"),
}
# max 系の下限フロア（良品で常に0に近い指標が過敏にならないように）
_MAX_FLOOR = {"clip_high_max": 0.05, "clip_low_max": 0.05, "glare_max": 0.02,
              "center_offset_max": 0.12}


def collect_metrics(images: Sequence[Image.Image]) -> Dict[str, np.ndarray]:
    """画像群から各メトリクスの配列を収集する。"""
    acc: Dict[str, List[float]] = {k: [] for k in METRIC_SPEC}
    for im in images:
        m = assess_quality(im, **{k: -1e9 if "min" in k or k.endswith("_min") else 1e9
                                  for k in DEFAULTS}).metrics  # 全通過させ純粋に測定
        for k in acc:
            if k in m:
                acc[k].append(float(m[k]))
    return {k: np.array(v, dtype=np.float64) for k, v in acc.items() if v}


def recommend_thresholds(good: Dict[str, np.ndarray], p_low: float = 1.0,
                         p_high: float = 99.0, margin: float = 0.10) -> Dict[str, float]:
    """良品分布から推奨しきい値を導出する。"""
    rec: Dict[str, float] = {}
    for metric, (direction, key) in METRIC_SPEC.items():
        if metric not in good or good[metric].size == 0:
            continue
        arr = good[metric]
        if direction == "min":
            thr = float(np.percentile(arr, p_low)) * (1.0 - margin)
            rec[key] = max(0.0, thr)
        elif direction == "max":
            thr = float(np.percentile(arr, p_high)) * (1.0 + margin)
            rec[key] = max(thr, _MAX_FLOOR.get(key, 0.0))
        else:  # range
            lo_key, hi_key = key
            rec[lo_key] = max(0.0, float(np.percentile(arr, p_low)) * (1.0 - margin))
            rec[hi_key] = min(1.0, float(np.percentile(arr, p_high)) * (1.0 + margin)) \
                if metric != "brightness" else float(np.percentile(arr, p_high)) * (1.0 + margin)
    return rec


def _reject_rate(images: Sequence[Image.Image], thresholds: Dict[str, float]) -> float:
    if not images:
        return float("nan")
    rej = sum(0 if assess_quality(im, **thresholds).ok else 1 for im in images)
    return rej / len(images)


def calibrate(good_images: Sequence[Image.Image],
              bad_images: Optional[Sequence[Image.Image]] = None,
              p_low: float = 1.0, p_high: float = 99.0, margin: float = 0.10) -> dict:
    """良品（必須）・不良（任意）からしきい値を導出し、検証レポートを返す。"""
    good = collect_metrics(good_images)
    rec = recommend_thresholds(good, p_low, p_high, margin)
    merged = {**DEFAULTS, **rec}

    report = {
        "n_good": len(good_images),
        "n_bad": len(bad_images) if bad_images else 0,
        "recommended": {k: round(v, 6) for k, v in rec.items()},
        "good_metric_stats": {
            k: {"p1": round(float(np.percentile(v, 1)), 6),
                "median": round(float(np.median(v)), 6),
                "p99": round(float(np.percentile(v, 99)), 6)}
            for k, v in good.items()
        },
        "validation": {
            "good_reject_rate": round(_reject_rate(good_images, merged), 4),
            "bad_reject_rate": round(_reject_rate(bad_images, merged), 4) if bad_images else None,
        },
    }
    return {"thresholds": merged, "recommended": rec, "report": report}


def calibrate_dirs(good_dir, bad_dir=None, **kw) -> dict:
    """ディレクトリの画像からキャリブレーションする。"""
    exts = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}

    def _load(d):
        return [load_image(p) for p in sorted(Path(d).rglob("*"))
                if p.suffix.lower() in exts]

    good = _load(good_dir)
    bad = _load(bad_dir) if bad_dir else None
    if not good:
        raise RuntimeError(f"良品画像が見つかりません: {good_dir}")
    return calibrate(good, bad, **kw)


def save_thresholds(thresholds: Dict[str, float], path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(thresholds, f, ensure_ascii=False, indent=2)


# ---- 合成デモ用の良品/不良画像生成（スクリプトと API で共用） ----
def degrade(img: Image.Image, kind: str, rng) -> Image.Image:
    """良品画像を意図的に劣化させる（キャリブレーション検証用）。"""
    from PIL import ImageEnhance, ImageFilter

    if kind == "blur":
        return img.filter(ImageFilter.GaussianBlur(rng.uniform(3.0, 5.0)))
    if kind == "dark":
        return ImageEnhance.Brightness(img).enhance(rng.uniform(0.12, 0.22))
    if kind == "bright":
        return ImageEnhance.Brightness(img).enhance(rng.uniform(1.6, 2.2))
    if kind == "glare":
        a = np.asarray(img.convert("L"), dtype=np.float32)
        c = int(a.shape[1] * rng.uniform(0.3, 0.7))
        a[:, max(0, c - 12):c + 12] = 255
        return Image.fromarray(a.astype(np.uint8)).convert("RGB")
    if kind == "offcenter":
        big = Image.new("RGB", (img.width + 120, img.height + 120), (200, 200, 200))
        big.paste(img, (110, 100))
        return big
    return img


def calibrate_demo(settings, n_parts: int = 30, n_groups: int = 8, seed: int = 5,
                   save: bool = False) -> dict:
    """現データセット（gen_config 優先）から良品/不良品を合成しキャリブレーションする。"""
    import json as _json

    from ..data.synth import generate_part_specs, render_part

    cfg_path = Path(settings.data_dir) / "metadata" / "gen_config.json"
    if cfg_path.exists():
        cfg = _json.loads(cfg_path.read_text(encoding="utf-8"))
        specs = generate_part_specs(cfg["n_parts"], cfg["n_groups"], cfg["seed"])
    else:
        specs = generate_part_specs(n_parts, n_groups, seed)

    rng = np.random.default_rng(0)
    good = [render_part(sp, seed=int(rng.integers(1, 10**8)))
            for sp in specs for _ in range(4)]
    kinds = ["blur", "dark", "bright", "glare", "offcenter"]
    bad = [degrade(render_part(sp, seed=int(rng.integers(1, 10**8)), jitter=False),
                   kinds[int(rng.integers(0, len(kinds)))], rng) for sp in specs]

    res = calibrate(good, bad)
    if save:
        save_thresholds(res["thresholds"], settings.quality_thresholds_path)
        res["saved_to"] = str(settings.quality_thresholds_path)
    return res
