#!/usr/bin/env python3
"""距離学習＋索引構築を実行する。

使い方:
    python scripts/20_build_index.py [--epochs 60] [--no-train]
"""
import argparse
import json

import _bootstrap  # noqa: F401
from partmatch.config import get_settings
from partmatch.pipeline import build_index


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--no-train", action="store_true", help="距離学習をスキップ")
    args = ap.parse_args()

    s = get_settings()
    summary = build_index(s, train=not args.no_train, epochs=args.epochs, verbose=True)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
