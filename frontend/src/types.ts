// FastAPI バックエンドのレスポンス型（src/partmatch/service と対応）

export type ResultKind = "OK" | "NG" | "REVIEW" | "RETAKE" | "UNKNOWN";

export interface Thresholds {
  accept: number;
  review: number;
  margin: number;
  similar_margin: number;
  top_k: number;
}

export interface EmbedderInfo {
  backbone: string;
  backbone_dim: number;
  projection: boolean;
  dim: number;
}

export interface Info {
  ready: boolean;
  embedder: EmbedderInfo;
  index_size: number;
  vector_backend: string | null;
  thresholds: Thresholds;
}

export interface Stats {
  n_parts: number;
  n_inspections: number;
  by_result: Partial<Record<ResultKind, number>>;
  avg_processing_ms: number | null;
}

export interface Part {
  id: number;
  part_no: string;
  part_name: string | null;
  category: string | null;
  material: string | null;
  group_id: number | null;
  status: string;
  accept_threshold: number | null;
  margin_threshold: number | null;
}

export interface Candidate {
  part_no: string;
  score: number;
  confidence: number;
  group_id: number | null;
}

export interface Quality {
  ok?: boolean;
  action?: string;
  issues?: string[];
  metrics?: Record<string, number>;
}

export interface InspectResponse {
  result: ResultKind;
  action: string;
  predicted_part_no: string | null;
  expected_part_no: string | null;
  confidence: number;
  margin: number;
  top_candidates: Candidate[];
  quality: Quality;
  reason: string;
  processing_time_ms: number;
  log_id: number | null;
}

export interface HistoryLog {
  id: number;
  expected_part_no: string | null;
  predicted_part_no: string | null;
  result: ResultKind;
  action: string;
  confidence: number | null;
  reason: string | null;
  created_at: string;
}

export interface BuildSummary {
  n_images: number;
  n_parts: number;
  dim: number;
  backend: string;
  train_summary?: { train_acc: number } | null;
}

export interface GenerateDemoResponse {
  index: BuildSummary;
  parts_synced: number;
  ready: boolean;
}

export interface PartUpsert {
  part_no: string;
  part_name?: string | null;
  category?: string | null;
  group_id?: number | null;
  status?: string;
  accept_threshold?: number | null;
  margin_threshold?: number | null;
}

export interface ThresholdUpdate {
  accept_threshold?: number;
  review_threshold?: number;
  margin_threshold?: number;
  similar_margin_threshold?: number;
  top_k?: number;
}

export interface SelfTestResult {
  n_parts_tested: number;
  correct_load: Record<ResultKind, number>;
  correct_load_rate: Record<ResultKind, number>;
  safety: {
    false_accept_count: number;
    false_accept_rate: number;
    mismatch_catch_rate: number;
    ok_precision: number;
  };
  latency_ms: { avg: number; p95: number };
}

export interface CalibrateResult {
  recommended: Record<string, number>;
  report: {
    n_good: number;
    n_bad: number;
    recommended: Record<string, number>;
    good_metric_stats: Record<string, { p1: number; median: number; p99: number }>;
    validation: { good_reject_rate: number; bad_reject_rate: number | null };
  };
  applied: boolean;
}
