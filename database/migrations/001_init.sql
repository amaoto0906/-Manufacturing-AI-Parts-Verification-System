-- ============================================================
-- 部品照合システム / PostgreSQL 本番スキーマ
-- ベクトル検索を Faiss/Milvus/Qdrant ではなく DB 内で行う場合は
-- pgvector 拡張を利用できる（部品数が中規模なら DB 統合が運用上有利）。
-- ============================================================

-- pgvector を使う場合（任意）
-- CREATE EXTENSION IF NOT EXISTS vector;

-- 品番マスタ
CREATE TABLE IF NOT EXISTS parts (
    id               BIGSERIAL PRIMARY KEY,
    part_no          TEXT UNIQUE NOT NULL,
    part_name        TEXT,
    category         TEXT,
    material         TEXT,
    group_id         INTEGER,
    status           TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','retired')),
    accept_threshold REAL,
    margin_threshold REAL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_parts_group ON parts(group_id);

-- 撮影条件
CREATE TABLE IF NOT EXISTS capture_conditions (
    id            BIGSERIAL PRIMARY KEY,
    camera_model  TEXT,
    lens          TEXT,
    lighting_type TEXT,
    distance      REAL,
    angle         REAL,
    background    TEXT,
    exposure      TEXT,
    note          TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 登録画像（+ 任意で埋め込みを pgvector 列に保持）
CREATE TABLE IF NOT EXISTS part_images (
    id                   BIGSERIAL PRIMARY KEY,
    part_id              BIGINT NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
    image_path           TEXT NOT NULL,
    capture_condition_id BIGINT REFERENCES capture_conditions(id),
    is_active            BOOLEAN NOT NULL DEFAULT TRUE,
    -- embedding         vector(256),   -- pgvector 利用時に有効化
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_images_part ON part_images(part_id);
-- pgvector の近似最近傍インデックス（利用時）
-- CREATE INDEX IF NOT EXISTS idx_images_embedding
--   ON part_images USING ivfflat (embedding vector_cosine_ops) WITH (lists = 200);

-- 照合ログ
CREATE TABLE IF NOT EXISTS inspection_logs (
    id                  BIGSERIAL PRIMARY KEY,
    expected_part_no    TEXT,
    predicted_part_no   TEXT,
    result              TEXT NOT NULL CHECK (result IN ('OK','NG','REVIEW','RETAKE','UNKNOWN')),
    action              TEXT NOT NULL,
    confidence          REAL,
    margin              REAL,
    top_candidates_json JSONB,
    quality_json        JSONB,
    reason              TEXT,
    image_path          TEXT,
    operator_id         TEXT,
    line_id             TEXT,
    processing_time_ms  REAL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_logs_result  ON inspection_logs(result);
CREATE INDEX IF NOT EXISTS idx_logs_created ON inspection_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_logs_line    ON inspection_logs(line_id, created_at);

-- フィードバック（再学習データ源）
CREATE TABLE IF NOT EXISTS feedback_logs (
    id                BIGSERIAL PRIMARY KEY,
    inspection_log_id BIGINT REFERENCES inspection_logs(id) ON DELETE SET NULL,
    correct_part_no   TEXT,
    feedback_type     TEXT CHECK (feedback_type IN ('confirm','correct','unknown')),
    comment           TEXT,
    created_by        TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 日次の判定内訳ビュー（精度監視ダッシュボード用）
CREATE OR REPLACE VIEW v_daily_result AS
SELECT date_trunc('day', created_at) AS day, line_id, result, COUNT(*) AS n
FROM inspection_logs
GROUP BY 1, 2, 3;
