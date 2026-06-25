# 02. システムアーキテクチャ

## 2.1 全体データフロー

```
撮影 → 画質ゲート → 特徴抽出(backbone) → 投影ヘッド(Metric Learning)
     → ベクトル検索(Faiss) → 品番集約 → 判定エンジン → API応答 → C#/PLC
                                                         ↘ 照合ログ/フィードバック(DB)
```

各段は疎結合で、PoC構成（classic + Faiss + SQLite + REST）から本番構成
（DINOv2 + Milvus + PostgreSQL + gRPC + TensorRT）へ段階移行できる。

## 2.2 レイヤーとモジュール対応

| レイヤー | 役割 | 実装 |
|----------|------|------|
| 入力・前処理 | 読込/EXIF補正/正方クロップ/コントラスト正規化 | `preprocess.py` |
| 画質ゲート | ピンボケ/露出/反射/位置/被覆を検査 | `quality/checks.py` |
| 特徴抽出 | 画像→埋め込み（差替可） | `backbones/{classic,torchvision,dinov2}.py` |
| 距離学習 | 照合に適した空間へ写像（ArcFace） | `metric_learning/` |
| ベクトル検索 | Top-K 近傍検索 | `index/store.py` |
| 判定 | 安全側の状態分類 | `matching/engine.py` |
| 永続化 | 品番/画像/ログ/FB | `db/repository.py` |
| API | REST（multipart） | `service/` |
| 管理UI | 運用画面 | `web/` |
| 連携 | 既存C# | `csharp-client/` |

## 2.3 なぜ「分類」でなく「照合（embedding + 検索）」か
2万品番を2万クラス分類にすると、(1) 新規品番追加で再学習が必要、(2) 少数データ品番が不安定、
(3) 類似品の識別境界が甘い、(4) 運用負荷が高い、という問題が出る。

本システムは **画像→特徴ベクトル→最近傍検索** とすることで：
- 新規品番は **登録画像の embedding を追加するだけ**（モデル再学習不要、F-08）
- 距離学習（ArcFace）でクラス内を密・クラス間を疎にし、類似品の識別を強化
- 複数枚登録＋品番単位集約で撮影ばらつきに頑健

## 2.4 判定エンジン（安全側設計の核）
1. 画質ゲート不合格 → **RETAKE**
2. Top-K 行を **品番単位に集約**（同一品番は最大スコアを採用）
3. `top1.score >= accept` かつ `margin(=top1-top2) >= req_margin` を「強い一致(strong)」と定義
4. 類似品番グループ内の僅差には **追加マージン** を要求（`similar_margin_threshold`）
5. 品番別しきい値を上書き適用
6. 期待品番あり：
   - 一致 & strong → **OK** / 一致だが弱い → **REVIEW**
   - 不一致 & strong（別品番が高信頼）→ **NG（取り違え）** / 不一致 & 弱い → **REVIEW**
7. 期待品番なし（オープン識別）：strong → **OK** / 中 → **REVIEW** / 低 → **UNKNOWN**

```
コサイン類似度: accept_threshold(0.62) ─ review_threshold(0.45)
マージン:       margin_threshold(0.06) ─ similar_margin_threshold(0.10)
```

## 2.5 スケーラビリティ（2万品番・1秒以内）
- 2万品番 × 数枚 = 数十万ベクトル。`IndexFlatIP`（厳密）でも CPU で 1秒以内に収まる規模。
- さらなる大規模化・低レイテンシ化は `IndexIVFFlat` / `IndexHNSWFlat` / Milvus / Qdrant へ。
- バックボーン推論は ONNX / TensorRT、GPU バッチ化で高速化。

## 2.6 可用性・フェイルセーフ
- AIサーバ停止時、C#側は**自動OKを出さず必ず要確認に倒す**（`Program.cs` 参照）。
- 照合ログは API/DB 双方で追跡可能。タイムアウト・リトライ・異常時処理を C# クライアントに実装。

## 2.7 デプロイ構成（例）
- オンプレGPU/産業用PC上に Docker でAPIを常駐（`docker-compose.yml`）。
- DB は PostgreSQL、画像は NAS/MinIO(S3互換)、監視は Prometheus/Grafana。
