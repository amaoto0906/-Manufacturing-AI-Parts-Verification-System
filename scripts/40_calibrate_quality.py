#!/usr/bin/env python3
"""画質ゲートしきい値を現場画像からキャリブレーションする。

実運用:
    python scripts/40_calibrate_quality.py --good-dir <良品画像> [--bad-dir <不良画像>] --save

デモ（実画像が無い場合、合成の良品/劣化画像で実証）:
    python scripts/40_calibrate_quality.py --demo
"""
import argparse
import io
import json

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

import _bootstrap  # noqa: F401
from partmatch.config import get_settings
from partmatch.data.synth import generate_part_specs, render_part
from partmatch.quality.calibrate import calibrate, calibrate_dirs, save_thresholds


def _degrade(img: Image.Image, kind: str, rng) -> Image.Image:
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


def _demo():
    s = get_settings()
    specs = generate_part_specs(30, 8, seed=5)
    rng = np.random.default_rng(0)
    good = [render_part(sp, seed=int(rng.integers(1, 10**8))) for sp in specs for _ in range(4)]
    bad = []
    kinds = ["blur", "dark", "bright", "glare", "offcenter"]
    for sp in specs:
        base = render_part(sp, seed=int(rng.integers(1, 10**8)), jitter=False)
        bad.append(_degrade(base, kinds[int(rng.integers(0, len(kinds)))], rng))
    print(f"良品 {len(good)} 枚 / 不良 {len(bad)} 枚 でキャリブレーション\n")
    res = calibrate(good, bad)
    print(json.dumps(res["report"], ensure_ascii=False, indent=2))
    print("\n=== 推奨しきい値（DEFAULTSを置換） ===")
    for k, v in res["recommended"].items():
        print(f"  {k:20s} = {v:.6f}")
    val = res["report"]["validation"]
    print(f"\n検証: 良品の誤棄却率 = {val['good_reject_rate']}  /  不良の棄却率 = {val['bad_reject_rate']}")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--good-dir")
    ap.add_argument("--bad-dir")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--save", action="store_true", help="しきい値をファイルへ保存")
    ap.add_argument("--p-low", type=float, default=1.0)
    ap.add_argument("--p-high", type=float, default=99.0)
    ap.add_argument("--margin", type=float, default=0.10)
    args = ap.parse_args()

    s = get_settings()
    if args.demo or not args.good_dir:
        res = _demo()
    else:
        res = calibrate_dirs(args.good_dir, args.bad_dir,
                             p_low=args.p_low, p_high=args.p_high, margin=args.margin)
        print(json.dumps(res["report"], ensure_ascii=False, indent=2))

    if args.save:
        save_thresholds(res["thresholds"], s.quality_thresholds_path)
        print(f"\n保存しました: {s.quality_thresholds_path}")
        print("→ MatchEngine が起動時に自動適用します。")


if __name__ == "__main__":
    main()
