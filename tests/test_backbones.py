"""classic バックボーンのテスト。"""
import numpy as np

from partmatch.backbones.classic import ClassicBackend
from partmatch.data.synth import generate_part_specs, render_part


def test_embedding_is_normalized():
    be = ClassicBackend()
    sp = generate_part_specs(4, 2, seed=1)[0]
    e = be.embed([render_part(sp, seed=1), render_part(sp, seed=2)])
    assert e.shape == (2, be.dim)
    assert np.allclose(np.linalg.norm(e, axis=1), 1.0, atol=1e-5)


def test_same_part_more_similar_than_different():
    be = ClassicBackend()
    specs = generate_part_specs(8, 3, seed=2)
    a1 = render_part(specs[0], seed=11)
    a2 = render_part(specs[0], seed=12)
    # 別グループの部品を選ぶ
    other = next(s for s in specs if s.group_id != specs[0].group_id)
    b1 = render_part(other, seed=13)
    e = be.embed([a1, a2, b1])
    sim_same = float(e[0] @ e[1])
    sim_diff = float(e[0] @ e[2])
    assert sim_same > sim_diff
