import { useEffect, useState } from "react";
import { api } from "../api";
import type { Info, ThresholdUpdate } from "../types";

const FIELDS: Array<{ key: keyof ThresholdUpdate; label: string; hint: string; step: number }> = [
  { key: "accept_threshold", label: "受理しきい値 (accept)", hint: "OK と判定する最低コサイン類似度", step: 0.01 },
  { key: "review_threshold", label: "要確認しきい値 (review)", hint: "これ未満は UNKNOWN へ", step: 0.01 },
  { key: "margin_threshold", label: "マージン (margin)", hint: "Top1-Top2 の最小差", step: 0.01 },
  { key: "similar_margin_threshold", label: "類似グループ追加マージン", hint: "同一グループ僅差時の要求差", step: 0.01 },
  { key: "top_k", label: "Top-K", hint: "返す候補数", step: 1 },
];

export function Settings() {
  const [info, setInfo] = useState<Info | null>(null);
  const [form, setForm] = useState<ThresholdUpdate>({});
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const i = await api.info();
      setInfo(i);
      setForm({
        accept_threshold: i.thresholds.accept,
        review_threshold: i.thresholds.review,
        margin_threshold: i.thresholds.margin,
        similar_margin_threshold: i.thresholds.similar_margin,
        top_k: i.thresholds.top_k,
      });
    } catch {
      setInfo(null);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const save = async () => {
    setBusy(true);
    setMsg("");
    try {
      const r = await api.updateThresholds(form);
      setMsg("更新しました（即時反映）。" + JSON.stringify(r.updated));
      await load();
    } catch (e) {
      setMsg("エラー: " + (e as Error).message);
    }
    setBusy(false);
  };

  return (
    <>
      <section className="surface">
        <div className="section-head">
          <div>
            <p className="eyebrow">Decision Thresholds</p>
            <h3>判定しきい値（実行時調整）</h3>
          </div>
          <button className="btn btn-primary btn-sm" onClick={save} disabled={busy}>
            {busy ? "更新中…" : "更新"}
          </button>
        </div>
        <div className="settings-grid">
          {FIELDS.map((f) => (
            <label key={f.key} className="setting">
              <span className="setting-label">{f.label}</span>
              <input
                type="number"
                step={f.step}
                value={form[f.key] ?? ""}
                onChange={(e) => setForm({ ...form, [f.key]: Number(e.target.value) })}
              />
              <span className="setting-hint">{f.hint}</span>
            </label>
          ))}
        </div>
        {msg && <p className="stats-note">{msg}</p>}
      </section>

      <section className="surface">
        <div className="section-head">
          <div>
            <p className="eyebrow">Model / Index</p>
            <h3>モデル・索引情報</h3>
          </div>
          <button className="btn btn-sm" onClick={load}>
            再読込
          </button>
        </div>
        <div className="kpi-grid">
          <div className="kpi">
            <div className="kpi-v">{info?.embedder.backbone ?? "-"}</div>
            <div className="kpi-l">バックボーン</div>
          </div>
          <div className="kpi">
            <div className="kpi-v">{info?.embedder.dim ?? "-"} 次元</div>
            <div className="kpi-l">埋め込み（投影{info?.embedder.projection ? "あり" : "なし"}）</div>
          </div>
          <div className="kpi">
            <div className="kpi-v">{info?.index_size ?? "-"}</div>
            <div className="kpi-l">登録ベクトル</div>
          </div>
          <div className="kpi">
            <div className="kpi-v">{info?.vector_backend ?? "-"}</div>
            <div className="kpi-l">検索エンジン</div>
          </div>
        </div>
        <p className="stats-note">
          バックボーンの切替（classic / torchvision / dinov2）は <code>.env</code> の
          <code> PARTMATCH_BACKEND</code> で行い、索引を再構築します（ダッシュボードの「索引再構築」）。
        </p>
      </section>
    </>
  );
}
