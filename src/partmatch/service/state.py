"""アプリケーション状態（シングルトン）。

設定・Embedder・ベクトルストア・判定エンジン・リポジトリを保持し、
索引の再構築（build-index）後に投影ヘッドとストアを再読み込みできる。
"""
from __future__ import annotations

from typing import Optional

from ..config import get_settings
from ..db.repository import Repository
from ..embedder import Embedder
from ..matching.engine import MatchEngine
from ..pipeline import load_store


class AppState:
    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.repo = Repository(self.settings.db_path)
        self.embedder = Embedder(self.settings)
        self.store = load_store(self.settings)
        self._engine: Optional[MatchEngine] = None
        self.rebuild_engine()

    def rebuild_engine(self) -> None:
        """投影ヘッド・ストア・品番別しきい値を再読込してエンジンを作り直す。"""
        self.embedder.reload_projection()
        self.store = load_store(self.settings)
        if self.store is not None:
            self._engine = MatchEngine(
                self.embedder, self.store, self.settings,
                part_thresholds=self.repo.part_thresholds(),
            )
        else:
            self._engine = None

    @property
    def engine(self) -> Optional[MatchEngine]:
        return self._engine

    @property
    def ready(self) -> bool:
        return self._engine is not None and self.store is not None and self.store.size > 0

    def info(self) -> dict:
        return {
            "ready": self.ready,
            "embedder": self.embedder.info,
            "index_size": self.store.size if self.store else 0,
            "vector_backend": self.store.backend if self.store else None,
            "thresholds": {
                "accept": self.settings.accept_threshold,
                "review": self.settings.review_threshold,
                "margin": self.settings.margin_threshold,
                "similar_margin": self.settings.similar_margin_threshold,
                "top_k": self.settings.top_k,
            },
        }


_state: Optional[AppState] = None


def get_state() -> AppState:
    global _state
    if _state is None:
        _state = AppState()
    return _state
