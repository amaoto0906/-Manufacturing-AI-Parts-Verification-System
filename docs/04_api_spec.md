# 04. API 仕様

ベースURL例: `http://127.0.0.1:8077` ／ OpenAPI: `/docs` ／ 管理UI: `/ui/`

既存C#システムからは REST（multipart）で照合を依頼する。低遅延が必要な場合は同等の
gRPC サービスへ差し替え可能（メッセージ定義は本仕様に準拠）。

## 4.1 照合

### POST `/api/v1/inspect`  （multipart/form-data）
| フィールド | 型 | 必須 | 説明 |
|------------|----|------|------|
| file | file | ✓ | 撮影画像（png/jpg等） |
| expected_part_no | string | | 作業指示の期待品番。空ならオープン識別 |
| operator_id | string | | 作業者ID |
| line_id | string | | ラインID |
| run_quality | bool | | 画質ゲート有効化（既定 true） |

**レスポンス（200）**
```json
{
  "result": "OK",
  "action": "pass",
  "predicted_part_no": "PRS-00001",
  "expected_part_no": "PRS-00001",
  "confidence": 0.889,
  "margin": 0.409,
  "top_candidates": [
    {"part_no": "PRS-00001", "score": 0.779, "confidence": 0.889, "group_id": 3},
    {"part_no": "PRS-00013", "score": 0.370, "confidence": 0.685, "group_id": 5}
  ],
  "quality": {"ok": true, "action": "pass", "issues": [], "metrics": {"blur": 0.0012}},
  "reason": "期待品番と一致し、信頼度・マージンとも十分。",
  "processing_time_ms": 25.5,
  "log_id": 1
}
```
`result` ∈ `OK|NG|REVIEW|RETAKE|UNKNOWN`、`action` ∈ `pass|block|manual_check|retake`。
HTTP 409 = 索引未構築、400 = 画像不正。

### POST `/api/v1/search-similar`  （期待品番なしの類似検索）
`file`, `top_k` を受け取り、オープン識別結果を返す。

## 4.2 品番マスタ
- `GET  /api/v1/parts?limit=1000` … 一覧
- `GET  /api/v1/parts/{part_no}` … 単体
- `POST /api/v1/parts` （JSON）… 登録/更新。`accept_threshold`/`margin_threshold` で品番別しきい値

```json
{"part_no":"PRS-00001","part_name":"ブラケットA","group_id":3,"accept_threshold":0.7,"margin_threshold":0.12}
```

## 4.3 管理
- `POST /api/v1/build-index` `{ "train": true, "epochs": 60 }` … 距離学習＋索引再構築
- `POST /api/v1/generate-demo` `{ "n_parts":40,"n_groups":10,"imgs_per_part":6,"epochs":50,"seed":42 }`
  … 合成データ生成→学習→索引→品番同期（デモ用）
- `GET  /api/v1/sample-image?part_no=PRS-00001&seed=0` … ホールドアウトのサンプル撮影画像PNG（デモ用）

## 4.3.1 運用・設定（ops）
- `POST /api/v1/settings/thresholds` … 判定しきい値を実行時更新（即時反映）
  `{ "accept_threshold":0.65, "margin_threshold":0.08, "review_threshold":..., "similar_margin_threshold":..., "top_k":5 }`（全て任意）
- `POST /api/v1/calibrate-quality` `{ "save": true }` … 合成の良品/不良品から画質しきい値を導出。
  `save=true` で `quality_thresholds.json` に保存し MatchEngine へ反映。レスポンスに推奨値と検証
  （良品誤棄却率・不良棄却率）を含む。
- `POST /api/v1/quality-thresholds/reset` … キャリブレーションを破棄し既定値へ戻す。
- `POST /api/v1/self-test` `{ "n_parts":20, "seed":0 }` … 稼働中モデルの自己診断（再学習なし）。
  正しい部品と取り違えを照合し、OK/REVIEW/NG 分布・**誤受理率・OK精度・取り違え検出率**・レイテンシを返す。

## 4.4 履歴・フィードバック・統計
- `GET  /api/v1/history?limit=100&result=NG` … 照合ログ
- `POST /api/v1/feedback` `{ "inspection_log_id":1,"feedback_type":"confirm|correct|unknown","correct_part_no":"PRS-..." }`
- `GET  /api/v1/feedback?limit=100`
- `GET  /api/v1/stats` … 件数・判定内訳・平均処理時間
- `GET  /api/v1/info` … 状態・バックボーン・索引サイズ・しきい値
- `GET  /health`

## 4.5 C# 連携例
`csharp-client/PartMatchingClient`（.NET 8）に `PartMatchingApiClient` を実装。
`action` を `LineAction` に変換し、`Pass=出荷可 / Block=出荷停止 / ManualCheck=要確認 / Retake=再撮影`
として設備制御する。AI停止時は **自動OKを出さず要確認に倒すフェイルセーフ**を実装済み。

## 4.6 gRPC 化の指針（本番）
`Inspect(InspectRequest) returns (InspectResponse)` を定義し、画像は `bytes`、結果は本仕様の
フィールドをそのまま proto 化。ストリーミングで連続照合に対応。
