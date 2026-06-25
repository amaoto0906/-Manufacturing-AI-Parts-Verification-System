// 型付き API クライアント（同一オリジン: 本番は /ui 配下、開発は Vite プロキシ経由）
import type {
  BuildSummary,
  CalibrateResult,
  GenerateDemoResponse,
  HistoryLog,
  Info,
  InspectResponse,
  Part,
  PartUpsert,
  SelfTestResult,
  Stats,
  ThresholdUpdate,
  Thresholds,
} from "./types";

async function req(path: string, opts?: RequestInit): Promise<Response> {
  const r = await fetch(path, opts);
  if (!r.ok) {
    let msg: string = String(r.status);
    try {
      msg = (await r.json()).detail ?? msg;
    } catch {
      /* noop */
    }
    throw new Error(msg);
  }
  return r;
}

const getJSON = <T>(p: string): Promise<T> => req(p).then((r) => r.json() as Promise<T>);
const postJSON = <T>(p: string, body: unknown): Promise<T> =>
  req(p, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then((r) => r.json() as Promise<T>);

export const api = {
  info: () => getJSON<Info>("/api/v1/info"),
  stats: () => getJSON<Stats>("/api/v1/stats"),
  parts: (limit = 1000) => getJSON<{ parts: Part[] }>(`/api/v1/parts?limit=${limit}`),
  history: (limit = 100, result = "") =>
    getJSON<{ logs: HistoryLog[] }>(
      `/api/v1/history?limit=${limit}${result ? `&result=${encodeURIComponent(result)}` : ""}`,
    ),

  generateDemo: (body: {
    n_parts: number;
    n_groups: number;
    imgs_per_part: number;
    epochs: number;
    seed: number;
  }) => postJSON<GenerateDemoResponse>("/api/v1/generate-demo", body),

  buildIndex: (epochs: number) =>
    postJSON<{ summary: BuildSummary; ready: boolean }>("/api/v1/build-index", {
      train: true,
      epochs,
    }),

  feedback: (body: {
    inspection_log_id: number;
    feedback_type: string;
    correct_part_no?: string;
    created_by?: string;
  }) => postJSON<{ id: number }>("/api/v1/feedback", body),

  upsertPart: (body: PartUpsert) =>
    postJSON<{ id: number; part_no: string }>("/api/v1/parts", body),

  updateThresholds: (body: ThresholdUpdate) =>
    postJSON<{ updated: Record<string, number>; thresholds: Thresholds }>(
      "/api/v1/settings/thresholds",
      body,
    ),

  selfTest: (n_parts: number, seed: number) =>
    postJSON<SelfTestResult>("/api/v1/self-test", { n_parts, seed }),

  calibrateQuality: (save: boolean) =>
    postJSON<CalibrateResult>("/api/v1/calibrate-quality", { save }),

  resetQuality: () => postJSON<{ reset: boolean }>("/api/v1/quality-thresholds/reset", {}),

  async sampleImage(partNo: string): Promise<Blob> {
    const r = await req(`/api/v1/sample-image?part_no=${encodeURIComponent(partNo)}&seed=0`);
    return r.blob();
  },

  async inspect(blob: Blob, expected: string, runQuality: boolean): Promise<InspectResponse> {
    const fd = new FormData();
    fd.append("file", blob, "capture.png");
    if (expected) fd.append("expected_part_no", expected);
    fd.append("run_quality", String(runQuality));
    fd.append("operator_id", "WEB");
    fd.append("line_id", "DEMO");
    const r = await req("/api/v1/inspect", { method: "POST", body: fd });
    return r.json() as Promise<InspectResponse>;
  },
};

export const pct = (v: number | null | undefined, digits = 0): string =>
  v == null ? "-" : `${(v * 100).toFixed(digits)}%`;
