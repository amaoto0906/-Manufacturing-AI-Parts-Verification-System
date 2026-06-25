import { useState } from "react";
import { api } from "../api";
import { asset } from "../assets";
import type { ResultKind, SelfTestResult } from "../types";

const ORDER: ResultKind[] = ["OK", "REVIEW", "NG", "RETAKE", "UNKNOWN"];
const COLOR: Record<ResultKind, string> = {
  OK: "var(--ok)",
  REVIEW: "var(--review)",
  NG: "var(--ng)",
  RETAKE: "var(--retake)",
  UNKNOWN: "var(--unknown)",
};

export function Report() {
  const [n, setN] = useState(20);
  const [res, setRes] = useState<SelfTestResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const run = async () => {
    setBusy(true);
    setErr("");
    try {
      setRes(await api.selfTest(n, 0));
    } catch (e) {
      setErr((e as Error).message);
    }
    setBusy(false);
  };

  const total = res ? res.n_parts_tested || 1 : 1;
  const safety = res?.safety;

  return (
    <>
      <section className="surface history-hero">
        <img src={asset("operations-wallboard.png")} alt="精度モニタ" />
        <div className="section-head">
          <div>
            <p className="eyebrow">Live Accuracy / Safety</p>
            <h3>精度レポート（自己診断）</h3>
          </div>
          <div className="filter-row">
            <label className="inline-label">
              品番数
              <input type="number" min={4} max={60} value={n} onChange={(e) => setN(Number(e.target.value))} />
            </label>
            <button className="btn btn-primary btn-sm" onClick={run} disabled={busy}>
              {busy ? "診断中…" : "診断実行"}
            </button>
          </div>
        </div>
        <p className="muted" style={{ margin: "0 0 4px" }}>
          稼働中のモデル・索引に対し、登録品番のホールドアウト撮影を生成して照合します（再学習なし・副作用なし）。
          正しい部品と「取り違え（別品番期待）」の両方を流し、誤受理率を測定します。
        </p>
      </section>

      {err && <div className="surface error-banner">エラー: {err}</div>}

      {res && (
        <div className="dashboard-grid">
          <section className="surface span-7">
            <div className="section-head">
              <div>
                <p className="eyebrow">Correct Load</p>
                <h3>正しい部品の判定内訳（{res.n_parts_tested} 件）</h3>
              </div>
            </div>
            <div className="breakdown">
              {ORDER.map((k) => {
                const v = res.correct_load[k] ?? 0;
                return (
                  <div className="brow" key={k}>
                    <span className="name">{k}</span>
                    <div className="track">
                      <div className="fill" style={{ width: `${((v / total) * 100).toFixed(0)}%`, background: COLOR[k] }} />
                    </div>
                    <span className="num">{v}</span>
                  </div>
                );
              })}
              <p className="stats-note">NG/REVIEW は誤出荷ではなく安全側の停止・要確認です。</p>
            </div>
          </section>

          <section className="surface span-5">
            <div className="section-head">
              <div>
                <p className="eyebrow">Safety KPI</p>
                <h3>安全指標</h3>
              </div>
            </div>
            <div className="kpi-grid">
              <KPI
                label="誤受理率（取り違えをOK）"
                value={safety ? (safety.false_accept_rate * 100).toFixed(1) + "%" : "-"}
                good={safety ? safety.false_accept_rate === 0 : false}
                hint="0 が要件"
              />
              <KPI
                label="OK精度"
                value={safety ? (safety.ok_precision * 100).toFixed(1) + "%" : "-"}
                good={safety ? safety.ok_precision >= 0.999 : false}
              />
              <KPI
                label="取り違え検出率"
                value={safety ? (safety.mismatch_catch_rate * 100).toFixed(1) + "%" : "-"}
                good={safety ? safety.mismatch_catch_rate >= 0.999 : false}
              />
              <KPI label="推論 avg / p95" value={res ? `${res.latency_ms.avg} / ${res.latency_ms.p95} ms` : "-"} good />
            </div>
          </section>
        </div>
      )}
    </>
  );
}

function KPI({ label, value, good, hint }: { label: string; value: string; good: boolean; hint?: string }) {
  return (
    <div className={`kpi ${good ? "kpi-good" : ""}`}>
      <div className="kpi-v">{value}</div>
      <div className="kpi-l">{label}</div>
      {hint && <div className="kpi-hint">{hint}</div>}
    </div>
  );
}
