"""pytest 共通設定。

テストは隔離された一時ディレクトリと軽量な classic バックボーンで実行し、
本番データ(var/)を汚さない。
"""
import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="partmatch_test_"))
os.environ.setdefault("PARTMATCH_BACKEND", "classic")
os.environ["PARTMATCH_DATA_DIR"] = str(_TMP / "data")
os.environ["PARTMATCH_MODELS_DIR"] = str(_TMP / "models")
os.environ["PARTMATCH_DB_PATH"] = str(_TMP / "pm.db")
os.environ["PARTMATCH_INDEX_PATH"] = str(_TMP / "models" / "index.faiss")
os.environ["PARTMATCH_PROJECTION_PATH"] = str(_TMP / "models" / "projection.npz")
