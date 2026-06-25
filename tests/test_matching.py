"""照合判定エンジン（安全側ロジック）のテスト。

バックボーンに依存せず、固定ベクトルを返す DummyEmbedder で判定分岐を検証する。
"""
import numpy as np
from PIL import Image

from partmatch.backbones.base import l2_normalize
from partmatch.config import get_settings
from partmatch.index.store import VectorStore
from partmatch.matching.engine import MatchEngine

IMG = Image.new("RGB", (64, 64), (120, 120, 120))


class DummyEmbedder:
    def __init__(self, dim):
        self.dim = dim
        self.vec = np.zeros(dim, dtype=np.float32)

    def set(self, raw):
        self.vec = l2_normalize(np.asarray(raw, dtype=np.float32))[0]
        return self

    def embed_one(self, image):
        return self.vec


def _orthogonal_store():
    s = VectorStore(4)
    s.add(l2_normalize(np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0]], dtype=np.float32)),
          [{"part_no": "A", "group_id": 1},
           {"part_no": "C", "group_id": 2},
           {"part_no": "D", "group_id": 3}])
    return s


def _engine(store):
    return MatchEngine(DummyEmbedder(4), store, get_settings())


def test_ok_when_match_and_confident():
    eng = _engine(_orthogonal_store())
    eng.embedder.set([1, 0, 0, 0])
    r = eng.inspect(IMG, expected_part_no="A", run_quality=False)
    assert r.result == "OK" and r.action == "pass"
    assert r.predicted_part_no == "A"


def test_ng_when_mismatch_and_confident():
    eng = _engine(_orthogonal_store())
    eng.embedder.set([1, 0, 0, 0])  # 実物は A だが期待は C
    r = eng.inspect(IMG, expected_part_no="C", run_quality=False)
    assert r.result == "NG" and r.action == "block"


def test_review_when_low_confidence():
    eng = _engine(_orthogonal_store())
    eng.embedder.set([0.55, 0, 0, 0.835])  # A へ cos~0.55（accept未満, review以上）
    r = eng.inspect(IMG, expected_part_no="A", run_quality=False)
    assert r.result == "REVIEW" and r.action == "manual_check"


def test_review_when_similar_group_small_margin():
    s = VectorStore(4)
    s.add(l2_normalize(np.array([[1, 0, 0, 0], [0.985, 0.174, 0, 0]], dtype=np.float32)),
          [{"part_no": "A", "group_id": 7}, {"part_no": "B", "group_id": 7}])
    eng = _engine(s)
    eng.embedder.set([0.996, 0.087, 0, 0])  # A,B どちらにも極めて近い（同一グループ・僅差）
    r = eng.inspect(IMG, expected_part_no="A", run_quality=False)
    assert r.result == "REVIEW"


def test_retake_on_bad_quality():
    eng = _engine(_orthogonal_store())
    eng.embedder.set([1, 0, 0, 0])
    # 一様画像 → コントラスト不足 → 画質ゲートで RETAKE
    r = eng.inspect(Image.new("RGB", (128, 128), (128, 128, 128)),
                    expected_part_no="A", run_quality=True)
    assert r.result == "RETAKE" and r.action == "retake"


def test_open_identification_without_expected():
    eng = _engine(_orthogonal_store())
    eng.embedder.set([1, 0, 0, 0])
    r = eng.inspect(IMG, expected_part_no=None, run_quality=False)
    assert r.result == "OK"
    assert r.predicted_part_no == "A"
