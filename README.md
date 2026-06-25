# 部品照合システム（Part Matching AI System）

自動車部品メーカーの製造現場で、**約2万種類の金属プレス部品**を画像認識AIで自動照合し、
**出荷時の品番取り違えをゼロに近づける**ための、本番アーキテクチャをそのまま実装した
エンドツーエンド・リファレンスシステムです。

> 「良品/不良品の2値判定」ではなく、**大量の類似部品の中から正しい品番を特定する照合タスク**。
> 基盤モデル特徴 + 距離学習(Metric Learning) + ベクトル検索 + **安全側の判定ゲート**で構成します。

---

## 1. 設計の核心：「AI単体で99.99%」ではなく「安全ゲートで誤出荷ゼロ」

最も危険なのは *間違っているのに OK を出す誤出荷* です。本システムは AI に必ず1つの答えを
強制させず、信頼度・Top1-Top2マージン・類似品番グループを総合して次の5状態に分類します。

| 判定 | 意味 | 設備アクション |
|------|------|----------------|
| **OK** | 期待品番と一致・高信頼・十分なマージン | `pass` 出荷可 |
| **NG** | 別品番の可能性が高い（取り違えの疑い） | `block` 出荷停止・警報 |
| **REVIEW** | 曖昧（信頼度不足 / 僅差 / 類似グループ内） | `manual_check` 作業者確認 |
| **RETAKE** | 画質不良で判定不可 | `retake` 再撮影 |
| **UNKNOWN** | 登録品番に該当なし（未登録の可能性） | `manual_check` 確認 |

### 実測（ホールドアウト評価・過学習排除済み / CPU・mobilenet_v3_small）

| 指標 | 値 | 備考 |
|------|----|------|
| 検索 Top-1 / Top-3 | **0.83 / 0.94** | ほぼ全品番が類似ペアを持つ難条件 |
| 独立部品の Top-1 | **1.00** | 紛らわしい品番が無ければ完璧 |
| **誤受理率（取り違えをOKで通す率）** | **0.000** | ← 本システムの要件 |
| **OK精度（OK判定の正解率）** | **1.000** | OK と出したものは全て正しい |
| **取り違え検出率** | **1.000** | 取り違え150件すべてを NG/REVIEW で捕捉 |
| 推論レイテンシ avg / p95 | **12.8 / 15.1 ms** | 1秒要件を大幅クリア（CPU） |

> ポイント：生の Top-1 が 83% でも、**誤出荷は 0件**。曖昧な17%を REVIEW/NG に回すことで
> 「通したものは必ず正しい」を実現します。本番では DINOv2・産業用カメラ・撮影治具により
> OK率（自動化率）がさらに向上します。

---

## 2. クイックスタート

```bash
# 1) 仮想環境と依存パッケージ
make venv
make install            # CPU版 torch/torchvision も導入

# 2) データ生成 → 距離学習 → 索引構築 → 安全ベンチマーク
make demo

# 3) API + 管理UI を起動
make api                 # http://127.0.0.1:8077/ui/
```

GUIを使わずワンクリックで全工程を試すなら、API起動後に管理UIの
**「デモデータ生成＆学習」** ボタンを押すだけで、合成データ生成→学習→索引→照合まで実演できます。

### 管理UI（React + TypeScript + Vite）

UIは React/TS で実装され、`vite build` の静的成果物を FastAPI が `/ui` で配信します
（バックエンドは Python 1プロセスのまま、追加ランタイム不要）。

```bash
make ui-install     # 依存導入（初回のみ）
make ui-build       # frontend/dist を生成 → make api で /ui に反映
make ui-dev         # 開発サーバ(Vite, HMR)。/api は :8077 へプロキシ
```

`frontend/dist` が無い場合は従来のバニラUI（`web/`）が自動でフォールバック配信されます。

### カメラ撮影（PC / モバイル）

照合タブから **PC/モバイルのカメラで直接撮影**して照合できます（`getUserMedia`）。
- **PC**：`http://127.0.0.1:8077/ui/`（localhost はセキュアコンテキスト扱い）でそのまま動作。
- **モバイル**：カメラ(getUserMedia)は **HTTPS が必須**。下記で HTTPS 起動し、スマホから
  `https://<PCのLAN-IP>:8443/ui/` を開く（自己署名のため初回は警告を承認）。

```bash
make gen-cert     # 自己署名証明書を certs/ に生成（localhost / 127.0.0.1 / LAN-IP）
make api-https    # https://<LAN-IP>:8443/ui/ で起動（モバイルのカメラ撮影に対応）
```

> なお、モバイルではHTTP環境でも、ファイル選択の `capture` 属性によりネイティブカメラ起動での
> 撮影は可能です（ライブプレビューの getUserMedia のみ HTTPS が必要）。

CLIから直接：

```bash
python scripts/10_generate_dataset.py --parts 60 --groups 15 --imgs 6
python scripts/20_build_index.py --epochs 60
python scripts/30_benchmark.py --parts 50 --groups 12
python scripts/40_calibrate_quality.py --demo   # 画質しきい値の自動キャリブレーション
pytest -q
```

C# 連携サンプル（既存システムからの呼び出し）：

```bash
cd csharp-client/PartMatchingClient
dotnet run -- ./capture.png PRS-00001 http://127.0.0.1:8077
```

---

## 3. システム構成

```
[産業用カメラ + 照明 + 治具]            ← docs/03_camera_lighting_design.md
        │ 撮影画像
        ▼
[画質ゲート]  ピンボケ/露出/反射/位置ズレ/部品不在を検査 → NGなら RETAKE
        │
        ▼
[特徴抽出バックボーン(差替可)]  classic | torchvision(CNN) | DINOv2(本番推奨)
        │ 埋め込み (L2正規化)
        ▼
[投影ヘッド / Metric Learning(ArcFace)]  照合に適した距離空間へ写像
        │ 256次元ベクトル
        ▼
[ベクトル検索  Faiss / (Milvus・Qdrant・pgvector)]  2万品番・Top-K・1秒以内
        │ Top-K 行 → 品番単位に集約
        ▼
[判定エンジン]  受理しきい値 + Top1-Top2マージン + 類似グループ + 品番別しきい値
        │ OK / NG / REVIEW / RETAKE / UNKNOWN
        ▼
[FastAPI(REST/gRPC化可)] ──→ [既存C#システム / PLC / 出荷管理]
        │
        ▼
[SQLite/PostgreSQL]  照合ログ・フィードバック（再学習データ源）・品番マスタ
```

詳細は [docs/02_system_architecture.md](docs/02_system_architecture.md)。

---

## 4. 差し替え可能なバックボーン（PoC→本番）

| backend | 依存 | 用途 | 実測 Top-1 / 誤受理率 / 速度 |
|---------|------|------|------|
| `classic` | numpy/PIL のみ | オフライン・フォールバック | 0.45 / 0.008 / **3.9ms** |
| `torchvision` | torch | **既定**・PoC〜本番 | 0.70 / 0.008 / 33.7ms |
| `dinov2` | torch + hub | **本番推奨** | **0.83 / 0.000 / 147.9ms** |

> 同一条件（40品番/12グループ, CPU）の比較。DINOv2 はこの難条件で唯一 **誤受理0・OK精度1.0・
> 取り違え検出率1.0** を達成（詳細 [docs/07](docs/07_model_and_metrics.md)）。

`.env` の `PARTMATCH_BACKEND` を変えるだけで切り替わります（推論コードは共通）。
**距離学習の投影ヘッドは torch で学習し、推論は純 numpy** で適用するため、`classic` 経路は
推論時に torch すら不要です。

---

## 5. リポジトリ構成

```
部品照合システム/
├── src/partmatch/            # コアパッケージ
│   ├── backbones/            # classic / torchvision / dinov2（差替可）
│   ├── quality/              # 画質ゲート
│   ├── metric_learning/      # 投影ヘッド + ArcFace（学習=torch / 推論=numpy）
│   ├── index/                # ベクトル検索（Faiss + numpyフォールバック）
│   ├── matching/             # 判定エンジン（OK/NG/REVIEW/RETAKE）★安全設計の核
│   ├── data/                 # 合成データ生成（類似品番グループ）
│   ├── db/                   # SQLite リポジトリ + スキーマ
│   ├── service/              # FastAPI（routers: inspect/parts/admin/feedback/health）
│   ├── embedder.py           # backbone + 投影ヘッド
│   ├── pipeline.py           # 収集→埋め込み→学習→索引 一気通貫
│   └── benchmark.py          # 安全指標ベンチマーク
├── frontend/                 # 管理UI（React + TypeScript + Vite, /ui で配信）
│   └── src/                  #   components/（Dashboard/Inspect/Parts/History 他）, api.ts, types.ts
├── web/                      # 旧バニラUI（フォールバック: frontend/dist 未ビルド時に配信）
├── csharp-client/            # 既存C#連携サンプル(.NET 8)
├── database/                 # PostgreSQL 本番スキーマ + migrations
├── scripts/                  # CLI（生成/構築/ベンチ/起動）
├── tests/                    # pytest（19件）
└── docs/                     # 要件/構成/撮影設計/API仕様/運用/開発計画/モデル指標
```

---

## 6. 本番への発展（拡張計画）

1. **単一ライン・数百品番** で現場実用性を確認（PoC）
2. **2万品番へ拡張** … バックボーンを DINOv2 へ、検索を Milvus/Qdrant へ、API を gRPC へ、
   推論を ONNX/TensorRT で最適化（[docs/06_development_plan.md](docs/06_development_plan.md)）
3. **複数拠点・複数ライン** へ標準化展開
4. **継続学習基盤** … 現場の「正解/誤判定/要確認」を蓄積し定期再学習（フィードバックAPI実装済み）
5. **品質管理・予防保全への応用** … 取り違え多発品番の分析、出荷ミス予兆検知

詳細ドキュメント:
[要件](docs/01_requirements.md) ・
[アーキテクチャ](docs/02_system_architecture.md) ・
[撮影環境設計](docs/03_camera_lighting_design.md) ・
[API仕様](docs/04_api_spec.md) ・
[運用マニュアル](docs/05_operation_manual.md) ・
[開発計画](docs/06_development_plan.md) ・
[モデルと評価指標](docs/07_model_and_metrics.md)

---

## 7. 動作環境

- Python 3.10+（本リポジトリは 3.12 で検証）
- CPU で動作（GPU 任意）。RAM 4GB+ で PoC 可能
- 主要依存: numpy / pillow / fastapi / uvicorn / faiss-cpu /（任意）torch・torchvision
- すべてのテスト（19件）は CPU・classic バックボーンで約5秒で完走
