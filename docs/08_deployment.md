# 08. デプロイ

## 8.0 重要：Vercel 単体では動かない
本システムは **常駐する Python ML サーバ（FastAPI + PyTorch + faiss）** と **ローカル状態
（`var/`：SQLite・索引・モデル）** を持つ。Vercel は静的サイト＋短命なサーバレス関数専用で、
(1) 常駐プロセス不可、(2) 関数サイズ上限（torch が入らない）、(3) 永続FS無し、のため
**バックエンドを Vercel に載せることはできない**。

選択肢は2つ。

---

## 8.1 推奨：単一コンテナ（Vercel 不要・最も簡単）
バックエンドは自分で React UI を `/ui` 配信できる。Dockerfile はマルチステージで
**React をビルドして同梱**するので、**イメージ1つ**を以下のいずれかに置けば全部動く。

対象: **Render / Railway / Fly.io / 任意のVM**（Docker対応・常駐プロセス可）

### メモリの注意
- 既定 `PARTMATCH_BACKEND=torchvision` は **約1.5〜2GB RAM** 必要。
- 無料/小規模枠(512MB)では **`PARTMATCH_BACKEND=classic`**（numpy/PILのみ・torch不要）にする。
  classic でも全機能が動作する（精度は docs/07 参照）。

### 状態の永続化
- `var/` 相当は環境変数で `/data` に集約済み。**永続ディスクを `/data` にマウント**する。
- 初回はデータ未生成（`ready:false`）。UIの「デモデータ生成＆学習」または
  `POST /api/v1/generate-demo` で索引を構築する（永続ディスクがあれば再起動後も保持）。

### 例: Render
1. New → **Web Service** → リポジトリ接続 → **Docker**。
2. Instance: 2GB以上（または `PARTMATCH_BACKEND=classic` で 512MB）。
3. **Disk** を追加し Mount Path = `/data`（例 1GB）。
4. 環境変数（任意）: `PARTMATCH_BACKEND=classic` など。Render は `PORT` を注入し、
   Dockerfile の `CMD` が `${PORT}` を使う。
5. デプロイ後 `https://<service>.onrender.com/ui/` を開き、デモ生成→照合。

### 例: Fly.io
```bash
fly launch --no-deploy            # fly.toml 生成（internal_port=8077 等に調整）
fly volumes create data --size 1  # /data 用
fly deploy
```

---

## 8.2 Vercel を使う：フロントだけ Vercel + バックは別ホスト
どうしても Vercel を使う場合、**フロントエンド(静的SPA)のみ** を Vercel に載せ、
バックエンドは 8.1 のコンテナホストに置き、Vercel の rewrite で `/api` を中継する。

### 手順
1. バックエンドを 8.1 でデプロイし URL を得る（例 `https://partmatch.onrender.com`）。
2. リポジトリ直下の **`vercel.json`** の `YOUR-BACKEND-HOST` をそのURLに置換。
   ```json
   "rewrites": [
     { "source": "/api/:path*", "destination": "https://partmatch.onrender.com/api/:path*" },
     { "source": "/health",     "destination": "https://partmatch.onrender.com/health" }
   ]
   ```
3. Vercel プロジェクトの **Environment Variables** に `VITE_BASE=/` を追加
   （Vercel はルート配信のため。未設定だと `/ui/` 基準になり資産パスが壊れる）。
4. Vercel はリポジトリ直下の `vercel.json` を使い、`frontend/` をビルドして `frontend/dist` を配信する。
   - installCommand: `npm --prefix frontend install`
   - buildCommand: `npm --prefix frontend run build`
   - outputDirectory: `frontend/dist`
5. デプロイ。`/api/*` は rewrite でバックエンドへ（同一オリジン扱いになり CORS 不要）。

> 注意：rewrite を使わず `VITE_API_BASE` でフルURL指定も可能だが、その場合バックエンド側の
> CORS 許可が必要（`service/app.py` は既に `allow_origins=["*"]`）。

---

## 8.2.1 クライアントに公開URLを送る（デモ閲覧用）

### A) 常時アクセスできる公開URL（推奨）= Render Blueprint
クライアントがいつ開いても動くよう、**オートシード**（起動時に索引を自動構築）を使う。
1. リポジトリ直下の **`render.yaml`** を用意済み（`PARTMATCH_AUTOSEED=1` + 省メモリ classic）。
2. Render → **New → Blueprint** → リポジトリ選択 → デプロイ。
3. 数十秒後 `https://partmatch-demo.onrender.com/ui/` がそのまま動くデモになる（索引構築済み）。
4. この URL をクライアントに送る。
- 無料枠(512MB)は classic + 投影なしで動作（torch を読み込まない）。15分無アクセスで休止し、
  次アクセス時にコールドスタート（数十秒）。高精度にするなら 2GB 枠 + torchvision。

### B) 今すぐ一時的に見せる（デプロイ不要・トンネル）
ローカルで起動中のサーバ(8077)を公開URLにする。**商談・ライブデモ向き**（常時公開ではない）。
```bash
# 1) ローカル起動（別ターミナル）
make api                                   # http://127.0.0.1:8077

# 2-a) cloudflared（要インストール・推奨）
cloudflared tunnel --url http://localhost:8077
#   → https://xxxx.trycloudflare.com が発行される

# 2-b) インストール不要（SSHのみ）
ssh -R 80:localhost:8077 nokey@localhost.run
#   → https://xxxx.lhr.life が発行される
```
発行された `https://.../ui/` をクライアントに送る。PCを起動したまま・トンネル実行中のみ有効。

### オートシードを手元で確認
```bash
PARTMATCH_AUTOSEED=1 make api    # 索引が無ければ起動時に自動構築 → 即 ready
```

## 8.3 まとめ
| 方式 | 構成 | 向き |
|------|------|------|
| **単一コンテナ(推奨)** | Docker 1つを Render/Railway/Fly/VM | 最も簡単・状態保持・全機能 |
| Vercel + 別バック | フロント=Vercel / バック=コンテナ | Vercelを使いたい場合 |
| Vercel 単体 | — | **不可**（ML常駐サーバを載せられない） |
