"""金属プレス部品を模した合成データ生成器。

実部品画像が手元に無い環境でも、照合パイプライン全体（学習→索引→照合）を
エンドツーエンドで検証できるようにする。重要なのは「類似品番グループ」を
意図的に作る点：同じ基本形状でも穴位置やノッチがわずかに違う部品を生成し、
現実の最難課題（似た部品の取り違え）を再現する。

各部品は複数枚の「撮影画像」を持ち、回転・拡縮・位置ズレ・明暗・ノイズ・
反射といった撮影ばらつきを付与する。numpy + PIL のみで動作。
"""
from __future__ import annotations

import csv
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SHAPES = ["rect", "rrect", "circle", "ring", "lshape", "bracket"]
_CANVAS = 256
_BG = 200       # コンベア相当の明るい背景
_BODY = 105     # 部品本体（中間グレー）
_EDGE = 60      # 外縁


@dataclass
class PartSpec:
    part_no: str
    group_id: int
    shape: str
    w: float
    h: float
    corner: float
    holes: List[Tuple[float, float, float]] = field(default_factory=list)  # (cx,cy,r) 比率
    notches: List[Tuple[str, float, float]] = field(default_factory=list)  # (side,pos,size)
    base_angle: float = 0.0

    def to_row(self) -> dict:
        return {
            "part_no": self.part_no,
            "group_id": self.group_id,
            "shape": self.shape,
            "w": round(self.w, 3),
            "h": round(self.h, 3),
            "n_holes": len(self.holes),
            "n_notches": len(self.notches),
        }


def _rng(seed: Optional[int]) -> np.random.Generator:
    return np.random.default_rng(seed)


def _make_base(rng: np.random.Generator, group_id: int) -> PartSpec:
    shape = SHAPES[rng.integers(0, len(SHAPES))]
    w = float(rng.uniform(0.45, 0.8))
    h = float(rng.uniform(0.45, 0.8))
    if shape in ("circle", "ring"):
        h = w
    corner = float(rng.uniform(0.0, 0.18))
    n_holes = int(rng.integers(1, 4))
    holes = []
    for _ in range(n_holes):
        holes.append((
            float(rng.uniform(-0.25, 0.25)),
            float(rng.uniform(-0.25, 0.25)),
            float(rng.uniform(0.04, 0.1)),
        ))
    notches = []
    if rng.random() < 0.5:
        side = ["top", "bottom", "left", "right"][rng.integers(0, 4)]
        notches.append((side, float(rng.uniform(-0.2, 0.2)), float(rng.uniform(0.08, 0.16))))
    return PartSpec("", group_id, shape, w, h, corner, holes, notches)


def _perturb(base: PartSpec, rng: np.random.Generator) -> PartSpec:
    """同一グループ内の「似ているが異なる」部品を作る。"""
    holes = [list(hc) for hc in base.holes]
    # 穴を1つ微小移動させる（取り違えやすい差異）
    if holes:
        i = rng.integers(0, len(holes))
        holes[i][0] += float(rng.uniform(-0.12, 0.12))
        holes[i][1] += float(rng.uniform(-0.12, 0.12))
    # まれに穴を増減
    r = rng.random()
    if r < 0.3 and len(holes) < 4:
        holes.append([float(rng.uniform(-0.25, 0.25)), float(rng.uniform(-0.25, 0.25)),
                      float(rng.uniform(0.04, 0.09))])
    elif r > 0.85 and len(holes) > 1:
        holes.pop()
    notches = list(base.notches)
    if rng.random() < 0.4:
        side = ["top", "bottom", "left", "right"][rng.integers(0, 4)]
        notches = [(side, float(rng.uniform(-0.2, 0.2)), float(rng.uniform(0.08, 0.16)))]
    return PartSpec("", base.group_id, base.shape,
                    base.w * float(rng.uniform(0.97, 1.03)),
                    base.h * float(rng.uniform(0.97, 1.03)),
                    base.corner, [tuple(h) for h in holes], notches)


def generate_part_specs(n_parts: int, n_groups: int, seed: int = 42) -> List[PartSpec]:
    """類似品番グループを含む n_parts 個の部品仕様を生成する。"""
    rng = _rng(seed)
    n_groups = max(1, min(n_groups, n_parts))
    specs: List[PartSpec] = []
    # 各グループにベースを1つ、残りを各グループへ分配
    bases = [_make_base(rng, g) for g in range(n_groups)]
    counts = [1] * n_groups
    for _ in range(n_parts - n_groups):
        counts[int(rng.integers(0, n_groups))] += 1
    for g, cnt in enumerate(counts):
        specs.append(bases[g])
        for _ in range(cnt - 1):
            specs.append(_perturb(bases[g], rng))
    rng.shuffle(specs)
    for i, sp in enumerate(specs):
        sp.part_no = f"PRS-{i + 1:05d}"
    return specs


def _draw_body(draw: ImageDraw.ImageDraw, spec: PartSpec, cx, cy, sw, sh, fill, outline):
    x0, y0, x1, y1 = cx - sw / 2, cy - sh / 2, cx + sw / 2, cy + sh / 2
    if spec.shape == "circle":
        draw.ellipse([x0, y0, x1, y1], fill=fill, outline=outline, width=3)
    elif spec.shape == "ring":
        draw.ellipse([x0, y0, x1, y1], fill=fill, outline=outline, width=3)
    elif spec.shape == "rrect":
        rad = int(min(sw, sh) * max(0.05, spec.corner))
        draw.rounded_rectangle([x0, y0, x1, y1], radius=rad, fill=fill, outline=outline, width=3)
    elif spec.shape == "lshape":
        draw.polygon([(x0, y0), (cx, y0), (cx, cy), (x1, cy), (x1, y1), (x0, y1)],
                     fill=fill, outline=outline)
    elif spec.shape == "bracket":
        draw.rectangle([x0, y0, x1, y1], fill=fill, outline=outline, width=3)
        draw.rectangle([cx - sw * 0.18, y0 + sh * 0.2, cx + sw * 0.18, y1], fill=_BG)
    else:  # rect
        draw.rectangle([x0, y0, x1, y1], fill=fill, outline=outline, width=3)


def render_part(spec: PartSpec, seed: Optional[int] = None, jitter: bool = True) -> Image.Image:
    """部品仕様から1枚の「撮影画像」を生成する。"""
    rng = _rng(seed)
    img = Image.new("L", (_CANVAS, _CANVAS), _BG)
    # 背景の僅かなムラ
    bg = np.asarray(img, dtype=np.float32)
    bg += rng.normal(0, 3, bg.shape)
    img = Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(img)

    cx = cy = _CANVAS / 2
    sw = spec.w * _CANVAS
    sh = spec.h * _CANVAS

    _draw_body(draw, spec, cx, cy, sw, sh, _BODY, _EDGE)
    # 中央リング穴
    if spec.shape == "ring":
        r = min(sw, sh) * 0.22
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=_BG)
    # 穴
    for hx, hy, hr in spec.holes:
        ax, ay = cx + hx * sw, cy + hy * sh
        rr = hr * min(sw, sh)
        draw.ellipse([ax - rr, ay - rr, ax + rr, ay + rr], fill=_BG, outline=_EDGE)
    # ノッチ
    for side, pos, size in spec.notches:
        ns = size * min(sw, sh)
        if side == "top":
            px = cx + pos * sw
            draw.rectangle([px - ns, cy - sh / 2 - 1, px + ns, cy - sh / 2 + ns], fill=_BG)
        elif side == "bottom":
            px = cx + pos * sw
            draw.rectangle([px - ns, cy + sh / 2 - ns, px + ns, cy + sh / 2 + 1], fill=_BG)
        elif side == "left":
            py = cy + pos * sh
            draw.rectangle([cx - sw / 2 - 1, py - ns, cx - sw / 2 + ns, py + ns], fill=_BG)
        else:
            py = cy + pos * sh
            draw.rectangle([cx + sw / 2 - ns, py - ns, cx + sw / 2 + 1, py + ns], fill=_BG)

    a = np.asarray(img, dtype=np.float32)

    if jitter:
        # 金属の鏡面反射ストライプ
        band = rng.uniform(0.2, 0.8)
        col = int(_CANVAS * band)
        width = int(_CANVAS * rng.uniform(0.04, 0.1))
        body_mask = a < (_BODY + _EDGE) / 2 + 30
        for off in range(-width, width):
            c = np.clip(col + off, 0, _CANVAS - 1)
            strip = np.zeros_like(a, dtype=bool)
            strip[:, c] = True
            a[strip & body_mask] += 55 * (1 - abs(off) / max(width, 1))
        a = np.clip(a, 0, 255)

    img = Image.fromarray(a.astype(np.uint8))

    if jitter:
        # 現場では位置決め治具で姿勢を拘束する前提（緩めに残す）
        angle = float(rng.uniform(-8, 8)) + spec.base_angle
        scale = float(rng.uniform(0.92, 1.06))
        img = img.rotate(angle, resample=Image.BILINEAR, fillcolor=_BG)
        ns = int(_CANVAS * scale)
        img = img.resize((ns, ns), Image.BILINEAR)
        # 位置ズレ込みで中央 _CANVAS を切り出し
        dx = int(rng.uniform(-0.06, 0.06) * _CANVAS)
        dy = int(rng.uniform(-0.06, 0.06) * _CANVAS)
        canvas = Image.new("L", (_CANVAS, _CANVAS), _BG)
        ox = (_CANVAS - ns) // 2 + dx
        oy = (_CANVAS - ns) // 2 + dy
        canvas.paste(img, (ox, oy))
        img = canvas
        # 明暗・ノイズ・軽いボケ
        arr = np.asarray(img, dtype=np.float32)
        arr = arr * float(rng.uniform(0.85, 1.15)) + float(rng.uniform(-12, 12))
        arr += rng.normal(0, rng.uniform(1, 5), arr.shape)
        img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        if rng.random() < 0.4:
            img = img.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 1.0)))

    return img.convert("RGB")


def generate_dataset(out_dir, n_parts: int = 60, n_groups: int = 15,
                     imgs_per_part: int = 6, seed: int = 42) -> dict:
    """データセットをディスクに生成する。

    返り値: 概要 dict（部品数・画像数・グループ数・パス）。
    """
    out = Path(out_dir)
    raw = out / "raw"
    meta = out / "metadata"
    # 旧データを除去して再生成（古い品番ディレクトリの残存による不整合を防ぐ）
    if raw.exists():
        shutil.rmtree(raw)
    raw.mkdir(parents=True, exist_ok=True)
    meta.mkdir(parents=True, exist_ok=True)

    specs = generate_part_specs(n_parts, n_groups, seed)
    rng = _rng(seed + 999)

    n_images = 0
    with (meta / "parts.csv").open("w", newline="", encoding="utf-8") as pf:
        writer = csv.DictWriter(pf, fieldnames=["part_no", "group_id", "shape", "w", "h",
                                                "n_holes", "n_notches"])
        writer.writeheader()
        for sp in specs:
            pdir = raw / sp.part_no
            pdir.mkdir(exist_ok=True)
            for k in range(imgs_per_part):
                im = render_part(sp, seed=int(rng.integers(0, 2**31)), jitter=True)
                im.save(pdir / f"img_{k:03d}.png")
                n_images += 1
            writer.writerow(sp.to_row())

    # 類似グループ表
    groups: dict = {}
    for sp in specs:
        groups.setdefault(sp.group_id, []).append(sp.part_no)
    with (meta / "similar_groups.csv").open("w", newline="", encoding="utf-8") as gf:
        gw = csv.writer(gf)
        gw.writerow(["group_id", "part_nos", "size"])
        for gid, members in sorted(groups.items()):
            gw.writerow([gid, ";".join(members), len(members)])

    # 生成条件を保存（sample-image でのジオメトリ再現に使用）
    with (meta / "gen_config.json").open("w", encoding="utf-8") as cf:
        json.dump({"n_parts": n_parts, "n_groups": n_groups, "seed": seed}, cf)

    return {
        "n_parts": len(specs),
        "n_groups": len([g for g in groups.values() if len(g) > 1]),
        "n_images": n_images,
        "raw_dir": str(raw),
        "metadata_dir": str(meta),
    }
