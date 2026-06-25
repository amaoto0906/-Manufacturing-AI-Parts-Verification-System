"""画質ゲートのテスト。"""
import numpy as np
from PIL import Image

from partmatch.data.synth import generate_part_specs, render_part
from partmatch.quality.checks import assess_quality


def test_good_image_passes():
    sp = generate_part_specs(4, 2, seed=1)[0]
    img = render_part(sp, seed=10, jitter=True)
    r = assess_quality(img)
    assert r.ok, r.issues
    assert r.action == "pass"


def test_uniform_image_fails_contrast():
    img = Image.new("RGB", (256, 256), (128, 128, 128))
    r = assess_quality(img)
    assert not r.ok
    assert r.action == "retake"
    assert any("コントラスト" in i for i in r.issues)


def test_dark_image_fails():
    img = Image.fromarray(np.full((256, 256, 3), 3, dtype=np.uint8))
    r = assess_quality(img)
    assert not r.ok
    assert any(("露出不足" in i) or ("黒つぶれ" in i) for i in r.issues)
