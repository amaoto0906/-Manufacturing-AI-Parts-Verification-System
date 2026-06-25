"""安全指標ベンチマーク。

「生の Top-1 精度」だけでなく、本システムの本質的価値である
「安全ゲートによる誤出荷ゼロ」を測定する:

    retrieval     : Top-1 / Top-3（検索性能）
    correct-load  : 正しい部品を流したとき OK/REVIEW/NG/RETAKE がどう出るか
    mismatch      : 作業指示と違う部品を流したとき（取り違え）、OK で通してしまう
                    割合（false-accept = 誤受理）。これが事実上ゼロであることが要件。
    latency       : 1件あたり推論時間（avg / p95）

ホールドアウト分割（ギャラリ画像と評価画像のシードを分離）で過学習を排除する。
"""
from __future__ import annotations

import time
from typing import List

import numpy as np

from .backbones import get_backbone
from .data.synth import generate_part_specs, render_part
from .embedder import Embedder
from .index.store import VectorStore
from .matching.engine import MatchEngine
from .metric_learning.head import apply_projection_np, load_projection_np


def live_self_test(settings, engine, n_parts: int = 20, seed: int = 0) -> dict:
    """稼働中モデル・索引に対する自己診断（再学習なし・副作用なし）。

    gen_config に基づき登録品番のホールドアウト撮影画像を生成し、(1) 正しい期待品番、
    (2) 取り違え（別品番期待）で照合して、OK/REVIEW/NG 分布・誤受理率・レイテンシを測る。
    """
    import json as _json
    import time
    from pathlib import Path

    from .data.synth import generate_part_specs, render_part

    cfg_path = Path(settings.data_dir) / "metadata" / "gen_config.json"
    if not cfg_path.exists():
        raise RuntimeError("gen_config がありません（合成データ未生成）。自己診断は合成データ前提です。")
    cfg = _json.loads(cfg_path.read_text(encoding="utf-8"))
    specs = generate_part_specs(cfg["n_parts"], cfg["n_groups"], cfg["seed"])
    part_nos = [sp.part_no for sp in specs]
    spec_of = {sp.part_no: sp for sp in specs}

    n = min(n_parts, len(specs))
    rng = np.random.default_rng(seed)
    targets = list(rng.choice(part_nos, size=n, replace=False))

    correct = {"OK": 0, "REVIEW": 0, "NG": 0, "RETAKE": 0, "UNKNOWN": 0}
    false_accept = 0
    ok_total = ok_correct = 0
    lat = []
    for pn in targets:
        img = render_part(spec_of[pn], seed=int(rng.integers(1, 10**8)))
        r = engine.inspect(img, expected_part_no=pn, run_quality=False)
        lat.append(r.processing_time_ms)
        correct[r.result] = correct.get(r.result, 0) + 1
        if r.result == "OK":
            ok_total += 1
            ok_correct += int(r.predicted_part_no == pn)
        # 取り違え
        wrong = pn
        while wrong == pn:
            wrong = part_nos[int(rng.integers(0, len(part_nos)))]
        img2 = render_part(spec_of[pn], seed=int(rng.integers(1, 10**8)))
        r2 = engine.inspect(img2, expected_part_no=wrong, run_quality=False)
        if r2.result == "OK":
            false_accept += 1

    return {
        "n_parts_tested": n,
        "correct_load": correct,
        "correct_load_rate": {k: round(v / n, 4) for k, v in correct.items()},
        "safety": {
            "false_accept_count": false_accept,
            "false_accept_rate": round(false_accept / n, 6),
            "mismatch_catch_rate": round(1.0 - false_accept / n, 6),
            "ok_precision": round(ok_correct / max(ok_total, 1), 6),
        },
        "latency_ms": {
            "avg": round(float(np.mean(lat)), 2),
            "p95": round(float(np.percentile(lat, 95)), 2),
        },
    }


def _split(specs, gallery_per, query_per, seed=123):
    rng = np.random.default_rng(seed)
    gal, gal_lab, qry, qry_lab = [], [], [], []
    for sp in specs:
        seeds = rng.integers(0, 10**8, size=gallery_per + query_per)
        for k in range(gallery_per):
            gal.append(render_part(sp, seed=int(seeds[k])))
            gal_lab.append(sp.part_no)
        for k in range(gallery_per, gallery_per + query_per):
            qry.append(render_part(sp, seed=int(seeds[k])))
            qry_lab.append(sp.part_no)
    return gal, gal_lab, qry, qry_lab


def run_benchmark(settings, n_parts=50, n_groups=12, gallery_per=5, query_per=3,
                  epochs=80, seed=7, train=True) -> dict:
    specs = generate_part_specs(n_parts, n_groups, seed)
    group_of = {sp.part_no: sp.group_id for sp in specs}

    gal, gal_lab, qry, qry_lab = _split(specs, gallery_per, query_per, seed=seed + 100)

    backbone = get_backbone(settings)
    base_gal = backbone.embed(gal)
    base_qry = backbone.embed(qry)

    # 距離学習（ギャラリのみで学習）
    proj = None
    if train and settings.use_projection:
        from .metric_learning.train import train_projection
        train_projection(base_gal, gal_lab, settings.projection_path,
                          out_dim=settings.projection_dim, epochs=epochs)
        proj = load_projection_np(settings.projection_path)
    elif settings.use_projection:
        proj = load_projection_np(settings.projection_path)

    G = apply_projection_np(base_gal, proj)
    Q = apply_projection_np(base_qry, proj)

    # 索引構築
    store = VectorStore(G.shape[1])
    store.add(G, [{"part_no": pn, "group_id": group_of[pn]} for pn in gal_lab])

    # --- 検索精度（部品単位 Top-K, 類似/独立 別） ---
    group_size = {}
    for sp in specs:
        group_size[sp.group_id] = group_size.get(sp.group_id, 0) + 1

    def topk_part(qvec, k):
        hits = store.search(qvec, k=40)
        seen, order = set(), []
        for h in hits:
            pn = h.meta["part_no"]
            if pn not in seen:
                seen.add(pn)
                order.append(pn)
            if len(order) >= k:
                break
        return order

    t1 = t3 = t1_sim = t1_dis = n_sim = n_dis = 0
    for v, lab in zip(Q, qry_lab):
        order = topk_part(v, 3)
        hit1 = order[:1] == [lab]
        hit3 = lab in order
        t1 += hit1
        t3 += hit3
        if group_size[group_of[lab]] > 1:
            n_sim += 1
            t1_sim += hit1
        else:
            n_dis += 1
            t1_dis += hit1
    nq = len(Q)

    # --- 判定エンジン評価（correct-load / mismatch） ---
    emb = Embedder(settings)
    emb.proj = proj
    eng = MatchEngine(emb, store, settings)

    rng = np.random.default_rng(seed + 7)
    correct = {"OK": 0, "REVIEW": 0, "NG": 0, "RETAKE": 0, "UNKNOWN": 0}
    mismatch = {"OK": 0, "REVIEW": 0, "NG": 0, "RETAKE": 0, "UNKNOWN": 0}
    ok_total = ok_correct = 0
    lat: List[float] = []
    all_parts = [sp.part_no for sp in specs]

    for img, lab in zip(qry, qry_lab):
        # 正しい部品を期待品番どおりに流す
        r = eng.inspect(img, expected_part_no=lab, run_quality=False)
        lat.append(r.processing_time_ms)
        correct[r.result] += 1
        if r.result == "OK":
            ok_total += 1
            ok_correct += int(r.predicted_part_no == lab)

        # 取り違え: 別の品番を期待して同じ画像を流す
        wrong = lab
        while wrong == lab:
            wrong = all_parts[int(rng.integers(0, len(all_parts)))]
        r2 = eng.inspect(img, expected_part_no=wrong, run_quality=False)
        mismatch[r2.result] += 1
        if r2.result == "OK":  # 取り違えを OK で通してしまった = 誤受理
            ok_total += 1
            # 期待(wrong)と一致して OK なら誤受理（実部品は lab）
            ok_correct += int(r2.predicted_part_no == lab and r2.predicted_part_no == wrong)

    false_accept = mismatch["OK"]
    catch_rate = 1.0 - false_accept / nq

    return {
        "config": {
            "backend": backbone.name, "dim": emb.dim, "vector_backend": store.backend,
            "n_parts": n_parts, "n_groups": n_groups,
            "gallery_per": gallery_per, "query_per": query_per, "n_query": nq,
            "trained": proj is not None,
        },
        "retrieval": {
            "top1": round(t1 / nq, 4), "top3": round(t3 / nq, 4),
            "top1_distinct": round(t1_dis / max(n_dis, 1), 4),
            "top1_similar": round(t1_sim / max(n_sim, 1), 4),
            "n_distinct": n_dis, "n_similar": n_sim,
        },
        "correct_load": {k: v for k, v in correct.items()},
        "correct_load_rate": {k: round(v / nq, 4) for k, v in correct.items()},
        "mismatch": {k: v for k, v in mismatch.items()},
        "safety": {
            "ok_precision": round(ok_correct / max(ok_total, 1), 6),
            "false_accept_count": false_accept,
            "false_accept_rate": round(false_accept / nq, 6),
            "mismatch_catch_rate": round(catch_rate, 6),
        },
        "latency_ms": {
            "avg": round(float(np.mean(lat)), 2),
            "p95": round(float(np.percentile(lat, 95)), 2),
            "max": round(float(np.max(lat)), 2),
        },
    }
