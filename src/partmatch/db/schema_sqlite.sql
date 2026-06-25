-- 部品照合システム / SQLite スキーマ（実行可能なデモ用）
-- 本番想定の PostgreSQL スキーマは database/schema_postgres.sql を参照。

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- 品番マスタ
CREATE TABLE IF NOT EXISTS parts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    part_no      TEXT UNIQUE NOT NULL,
    part_name    TEXT,
    category     TEXT,
    material     TEXT,
    group_id     INTEGER,                 -- 類似品番グループ
    status       TEXT NOT NULL DEFAULT 'active',  -- active | retired
    accept_threshold REAL,                -- 品番別しきい値（NULL=既定）
    margin_threshold REAL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_parts_group ON parts(group_id);

-- 登録画像
CREATE TABLE IF NOT EXISTS part_images (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    part_id       INTEGER NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
    image_path    TEXT NOT NULL,
    capture_condition_id INTEGER REFERENCES capture_conditions(id),
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_images_part ON part_images(part_id);

-- 撮影条件
CREATE TABLE IF NOT EXISTS capture_conditions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    camera_model TEXT,
    lens         TEXT,
    lighting_type TEXT,
    distance     REAL,
    angle        REAL,
    background   TEXT,
    exposure     TEXT,
    note         TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 照合ログ
CREATE TABLE IF NOT EXISTS inspection_logs (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    expected_part_no   TEXT,
    predicted_part_no  TEXT,
    result             TEXT NOT NULL,     -- OK | NG | REVIEW | RETAKE | UNKNOWN
    action             TEXT NOT NULL,     -- pass | block | manual_check | retake
    confidence         REAL,
    margin             REAL,
    top_candidates_json TEXT,
    quality_json       TEXT,
    reason             TEXT,
    image_path         TEXT,
    operator_id        TEXT,
    line_id            TEXT,
    processing_time_ms REAL,
    created_at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_logs_result ON inspection_logs(result);
CREATE INDEX IF NOT EXISTS idx_logs_created ON inspection_logs(created_at);

-- フィードバック（誤判定修正・再学習データ源）
CREATE TABLE IF NOT EXISTS feedback_logs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_log_id INTEGER REFERENCES inspection_logs(id) ON DELETE SET NULL,
    correct_part_no   TEXT,
    feedback_type     TEXT,               -- confirm | correct | unknown
    comment           TEXT,
    created_by        TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
