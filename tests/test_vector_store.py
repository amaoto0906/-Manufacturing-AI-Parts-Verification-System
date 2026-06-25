"""ベクトルストアのテスト。"""
import numpy as np

from partmatch.backbones.base import l2_normalize
from partmatch.index.store import VectorStore


def _store():
    s = VectorStore(4)
    v = l2_normalize(np.array([
        [1, 0, 0, 0],
        [0, 1, 0, 0],
        [0, 0, 1, 0],
    ], dtype=np.float32))
    s.add(v, [{"part_no": "A"}, {"part_no": "B"}, {"part_no": "C"}])
    return s


def test_search_returns_nearest():
    s = _store()
    q = l2_normalize(np.array([0.9, 0.1, 0, 0], dtype=np.float32))[0]
    hits = s.search(q, k=2)
    assert hits[0].meta["part_no"] == "A"
    assert hits[0].score > hits[1].score


def test_save_and_load(tmp_path):
    s = _store()
    path = tmp_path / "idx.faiss"
    s.save(path)
    s2 = VectorStore.load(path)
    assert s2.size == 3
    q = l2_normalize(np.array([0, 0, 1, 0], dtype=np.float32))[0]
    assert s2.search(q, k=1)[0].meta["part_no"] == "C"


def test_empty_store_returns_no_hits():
    s = VectorStore(4)
    assert s.search(np.zeros(4, dtype=np.float32), k=3) == []
