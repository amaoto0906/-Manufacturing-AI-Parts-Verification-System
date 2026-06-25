#!/usr/bin/env python3
"""合成データセットを生成する。

使い方:
    python scripts/10_generate_dataset.py [--parts 60] [--groups 15] [--imgs 6] [--seed 42]
"""
import argparse

import _bootstrap  # noqa: F401
from partmatch.config import get_settings
from partmatch.data.synth import generate_dataset


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", type=int, default=60)
    ap.add_argument("--groups", type=int, default=15)
    ap.add_argument("--imgs", type=int, default=6)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    s = get_settings()
    summary = generate_dataset(s.data_dir, n_parts=args.parts, n_groups=args.groups,
                               imgs_per_part=args.imgs, seed=args.seed)
    print("生成完了:", summary)


if __name__ == "__main__":
    main()
