"""画像の入出力と前処理。

撮影画像（バイト列・パス・PIL）を RGB の PIL 画像へ正規化する。
金属プレス部品は反射が強いため、本番では現場で撮影条件を固定する前提だが、
ここでは軽量なコントラスト正規化と中心クロップで頑健性を底上げする。
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Union

import numpy as np
from PIL import Image, ImageOps

ImageSource = Union[str, Path, bytes, bytearray, Image.Image]


def load_image(src: ImageSource) -> Image.Image:
    """各種ソースから RGB の PIL 画像を読み込む。"""
    if isinstance(src, Image.Image):
        img = src
    elif isinstance(src, (bytes, bytearray)):
        img = Image.open(io.BytesIO(bytes(src)))
    else:
        img = Image.open(str(src))
    # EXIF の回転を反映し、RGB に統一
    img = ImageOps.exif_transpose(img)
    return img.convert("RGB")


def center_square(img: Image.Image) -> Image.Image:
    """中央を正方形にクロップする（部品が中央にある前提）。"""
    w, h = img.size
    s = min(w, h)
    left = (w - s) // 2
    top = (h - s) // 2
    return img.crop((left, top, left + s, top + s))


def prepare(img: Image.Image, size: int = 224, autocontrast: bool = True) -> Image.Image:
    """バックボーン入力用に整形する。"""
    img = center_square(img)
    if autocontrast:
        img = ImageOps.autocontrast(img, cutoff=1)
    return img.resize((size, size), Image.BILINEAR)


def to_gray_array(img: Image.Image, size: int) -> np.ndarray:
    """グレースケール float32 配列 [0,1] を返す（classic バックボーン用）。"""
    g = center_square(img).convert("L").resize((size, size), Image.BILINEAR)
    return np.asarray(g, dtype=np.float32) / 255.0
