#!/usr/bin/env python3
"""安全指標ベンチマークを実行する。

生 Top-1/Top-3 だけでなく、誤受理率（取り違えを OK で通す率）・OK精度・
取り違え検出率・レイテンシを計測する。ホールドアウト評価で過学習を排除。

使い方:
    python scripts/30_benchmark.py [--parts 50] [--groups 12] [--epochs 80]
"""
import argparse
import json

import _bootstrap  # noqa: F401
from partmatch.config import get_settings
from partmatch.benchmark import run_benchmark


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", type=int, default=50)
    ap.add_argument("--groups", type=int, default=12)
    ap.add_argument("--gallery", type=int, default=6)
    ap.add_argument("--query", type=int, default=3)
    ap.add_argument("--epochs", type=int, default=80)
    args = ap.parse_args()

    s = get_settings()
    res = run_benchmark(s, n_parts=args.parts, n_groups=args.groups,
                        gallery_per=args.gallery, query_per=args.query, epochs=args.epochs)
    print(json.dumps(res, ensure_ascii=False, indent=2))

    saf = res["safety"]
    print("\n=== サマリ ===")
    print(f"  バックボーン      : {res['config']['backend']} ({res['config']['dim']}次元)")
    print(f"  検索 Top-1/Top-3  : {res['retrieval']['top1']} / {res['retrieval']['top3']}")
    print(f"  誤受理率(取り違え) : {saf['false_accept_rate']}  ← 0 が目標")
    print(f"  OK精度            : {saf['ok_precision']}")
    print(f"  取り違え検出率    : {saf['mismatch_catch_rate']}")
    print(f"  推論 avg/p95      : {res['latency_ms']['avg']} / {res['latency_ms']['p95']} ms")


if __name__ == "__main__":
    main()
