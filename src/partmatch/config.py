"""システム全体の設定。

環境変数 (PARTMATCH_*) または .env から読み込む。判定しきい値などの
安全に関わるパラメータを一元管理し、現場ごとのチューニングを容易にする。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# リポジトリルート（src/partmatch/config.py から2階層上）
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """アプリケーション設定。"""

    model_config = SettingsConfigDict(
        env_prefix="PARTMATCH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- バックボーン選択 ---
    # classic     : numpy/PIL のみ・追加DLなし（フォールバック / オフライン）
    # torchvision : 事前学習CNN特徴（既定・高精度・軽量）
    # dinov2      : 本番推奨。基盤モデルでさらに高い表現力
    backend: str = "torchvision"  # classic | torchvision | dinov2
    torchvision_arch: str = "mobilenet_v3_small"
    dinov2_arch: str = "dinov2_vits14"

    # --- 投影ヘッド（距離学習） ---
    projection_dim: int = 256
    use_projection: bool = True

    # --- 判定しきい値（安全側設計の中核） ---
    accept_threshold: float = 0.62
    review_threshold: float = 0.45
    margin_threshold: float = 0.06
    similar_margin_threshold: float = 0.10

    # --- 検索 ---
    top_k: int = 5

    # --- パス ---
    data_dir: Path = PROJECT_ROOT / "var" / "data"
    models_dir: Path = PROJECT_ROOT / "var" / "models"
    db_path: Path = PROJECT_ROOT / "var" / "partmatch.db"
    index_path: Path = PROJECT_ROOT / "var" / "models" / "index.faiss"
    projection_path: Path = PROJECT_ROOT / "var" / "models" / "projection.npz"
    # 現場でキャリブレーションした画質しきい値（存在すれば優先適用）
    quality_thresholds_path: Path = PROJECT_ROOT / "var" / "models" / "quality_thresholds.json"

    # --- 推論 ---
    device: str = "cpu"
    image_size: int = 224

    # --- 公開デモ用オートシード ---
    # true かつ索引が無ければ、起動時に合成データ生成→学習→索引構築を自動実行する。
    # クラウドにデプロイした直後からクライアントが動くデモを閲覧できるようにする。
    autoseed: bool = False
    autoseed_parts: int = 40
    autoseed_groups: int = 10
    autoseed_imgs: int = 6
    autoseed_epochs: int = 40

    def ensure_dirs(self) -> None:
        """必要なディレクトリを作成する。"""
        for p in (self.data_dir, self.models_dir, self.db_path.parent):
            Path(p).mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """シングルトン設定インスタンスを返す。"""
    s = Settings()
    s.ensure_dirs()
    return s
