# 部品照合システム 開発用 Makefile
PY ?= .venv/bin/python
PIP ?= .venv/bin/pip
PORT ?= 8077
export PYTHONPATH := src

.PHONY: help venv install demo dataset build benchmark api test clean ui-install ui-build ui-dev gen-cert api-https

help:
	@echo "make venv       - 仮想環境を作成"
	@echo "make install    - 依存パッケージを導入（CPU版torch含む）"
	@echo "make demo       - データ生成→学習→索引→ベンチマークを一括実行"
	@echo "make dataset    - 合成データ生成"
	@echo "make build      - 距離学習＋索引構築"
	@echo "make benchmark  - 安全指標ベンチマーク"
	@echo "make calibrate  - 画質しきい値の自動キャリブレーション（デモ）"
	@echo "make ui-install - フロントエンド(React)依存を導入"
	@echo "make ui-build   - フロントエンドをビルド (frontend/dist -> /ui で配信)"
	@echo "make ui-dev     - フロントエンド開発サーバ (Vite, APIは8077へプロキシ)"
	@echo "make api        - API + 管理UI 起動 (PORT=$(PORT))"
	@echo "make api-https  - HTTPS で起動 (モバイルのカメラ撮影に必要, 8443)"
	@echo "make gen-cert   - 自己署名証明書を生成 (certs/)"
	@echo "make test       - pytest 実行"
	@echo "make clean      - 生成物(var/)を削除"

venv:
	python3 -m venv .venv && $(PIP) install --upgrade pip

install:
	$(PIP) install -r requirements.txt
	$(PIP) install torch torchvision --index-url https://download.pytorch.org/whl/cpu

dataset:
	$(PY) scripts/10_generate_dataset.py --parts 60 --groups 15 --imgs 6

build:
	$(PY) scripts/20_build_index.py --epochs 60

benchmark:
	$(PY) scripts/30_benchmark.py --parts 50 --groups 12 --epochs 80

calibrate:
	$(PY) scripts/40_calibrate_quality.py --demo

demo: dataset build benchmark

ui-install:
	cd frontend && npm install

ui-build:
	cd frontend && npm run build

ui-dev:
	cd frontend && npm run dev

api:
	bash scripts/run_api.sh $(PORT)

gen-cert:
	bash scripts/gen_cert.sh

api-https:
	bash scripts/run_api_https.sh 8443

test:
	$(PY) -m pytest -q

clean:
	rm -rf var
