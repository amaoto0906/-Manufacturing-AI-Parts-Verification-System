"""部品照合システム (Part Matching AI System).

自動車部品メーカーの製造現場において、約2万種類の金属プレス部品を
画像認識AIで自動照合し、出荷時の品番取り違えを防ぐためのコアパッケージ。

主要レイヤー:
    backbones/        差し替え可能な特徴抽出バックボーン (classic/torchvision/dinov2)
    metric_learning/  距離学習（投影ヘッド + ArcFace）の学習パイプライン
    index/            ベクトル検索 (Faiss + numpy フォールバック)
    matching/         Top-K 照合と OK/NG/REVIEW/RETAKE 判定エンジン
    quality/          撮影画像の品質ゲート
    service/          FastAPI 推論サービス
    db/               照合ログ・品番マスタの永続化
"""

__version__ = "0.1.0"
