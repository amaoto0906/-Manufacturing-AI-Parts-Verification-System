import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { asset, mosaic, workflowCards } from "../assets";
import type { Info, ResultKind, Stats } from "../types";

const RESULT_ORDER: ResultKind[] = ["OK", "REVIEW", "NG", "RETAKE", "UNKNOWN"];
const RESULT_COLOR: Record<ResultKind, string> = {
  OK: "var(--ok)",
  REVIEW: "var(--review)",
  NG: "var(--ng)",
  RETAKE: "var(--retake)",
  UNKNOWN: "var(--unknown)",
};

interface Props {
  info: Info | null;
  offline: boolean;
  onRefresh: () => void;
}

export function Dashboard({ info, offline, onRefresh }: Props) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ n_parts: 40, n_groups: 10, imgs_per_part: 6, epochs: 50 });

  const loadStats = useCallback(async () => {
    try {
      setStats(await api.stats());
    } catch {
      setStats(null);
    }
  }, []);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  const addLog = (m: string) => setLog((p) => [`› ${m}`, ...p].slice(0, 40));

  const onGenerate = async () => {
    setBusy(true);
    addLog("デモデータ生成＋距離学習＋索引構築を実行中…");
    try {
      const r = await api.generateDemo({ ...form, seed: 42 });
      addLog(
        `完了: 部品 ${r.index.n_parts} / 画像 ${r.index.n_images} / 次元 ${r.index.dim} / 検索 ${r.index.backend}` +
          (r.index.train_summary ? ` / 学習acc ${r.index.train_summary.train_acc.toFixed(3)}` : ""),
      );
      await Promise.all([loadStats(), onRefresh()]);
    } catch (e) {
      addLog("エラー: " + (e as Error).message);
    }
    setBusy(false);
  };

  const onBuild = async () => {
    setBusy(true);
    addLog("索引再構築中…");
    try {
      const r = await api.buildIndex(form.epochs);
      addLog("索引再構築 完了: 部品 " + r.summary.n_parts + " / 画像 " + r.summary.n_images);
      await Promise.all([loadStats(), onRefresh()]);
    } catch (e) {
      addLog("エラー: " + (e as Error).message);
    }
    setBusy(false);
  };

  const th = info?.thresholds;
  const cards: Array<[string | number, string]> = offline
    ? [
        ["OFFLINE", "状態"],
        ["UI READY", "コンソール"],
        ["REST", "連携"],
        ["—", "登録ベクトル"],
        ["—", "検索エンジン"],
        ["安全ゲート", "判定"],
      ]
    : [
        [info?.ready ? "READY" : "未構築", "状態"],
        [info?.embedder.backbone ?? "-", "バックボーン"],
        [info?.index_size ?? 0, "登録ベクトル"],
        [`${info?.embedder.dim ?? "-"} 次元`, "埋め込み"],
        [info?.vector_backend ?? "-", "検索エンジン"],
        [`${th?.accept ?? "-"} / ${th?.margin ?? "-"}`, "受理 / マージン"],
      ];

  const total = stats ? Object.values(stats.by_result).reduce((a, b) => a + (b ?? 0), 0) || 1 : 1;

  return (
    <>
      <div className="operations-hero">
        <img src={asset("hero-inspection-cell.png")} alt="産業用カメラ照合セル" />
        <div className="hero-copy">
          <p className="eyebrow">Line DEMO / Safety Gate Active</p>
          <h2>画像照合から出荷可否までを一画面で制御</h2>
          <div className="hero-metrics">
            {cards.map(([v, l], i) => (
              <div className="icard" key={i}>
                <div className="v">{v}</div>
                <div className="l">{l}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="signal-stack" aria-hidden="true">
          <span className="signal ok"></span>
          <span className="signal warn"></span>
          <span className="signal stop"></span>
        </div>
      </div>

      <div className="dashboard-grid">
        <section className="surface span-7">
          <div className="section-head">
            <div>
              <p className="eyebrow">Inspection Flow</p>
              <h3>照合パイプライン</h3>
            </div>
            <span className="live-dot">LIVE</span>
          </div>
          <div className="workflow-strip">
            {workflowCards.map(([img, title, body], i) => (
              <article className="workflow-card" key={img} style={{ animationDelay: `${i * 60}ms` }}>
                <img src={asset(img)} alt={title} />
                <div>
                  <b>{title}</b>
                  <span>{body}</span>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="surface span-5">
          <div className="section-head">
            <div>
              <p className="eyebrow">Result Mix</p>
              <h3>判定内訳</h3>
            </div>
            <button className="icon-btn" title="更新" onClick={loadStats}>
              ↻
            </button>
          </div>
          <div className="breakdown">
            {RESULT_ORDER.map((k) => {
              const n = stats?.by_result[k] ?? 0;
              return (
                <div className="brow" key={k}>
                  <span className="name">{k}</span>
                  <div className="track">
                    <div
                      className="fill"
                      style={{ width: `${((n / total) * 100).toFixed(0)}%`, background: RESULT_COLOR[k] }}
                    ></div>
                  </div>
                  <span className="num">{n}</span>
                </div>
              );
            })}
            <p className="stats-note">
              {stats
                ? `総照合 ${stats.n_inspections} 件 / 平均 ${stats.avg_processing_ms ?? "-"} ms`
                : "APIに接続すると照合ログを表示します"}
            </p>
          </div>
        </section>
      </div>

      <div className="dashboard-grid">
        <section className="surface span-5 demo-panel">
          <div className="section-head">
            <div>
              <p className="eyebrow">Demo Training</p>
              <h3>デモデータ生成と索引構築</h3>
            </div>
          </div>
          <div className="demo-visual-grid">
            <img src={asset("data-generation.png")} alt="合成データ生成" />
            <img src={asset("metric-learning.png")} alt="距離学習" />
          </div>
          <div className="form-row dense">
            {(
              [
                ["品番数", "n_parts"],
                ["類似Gr", "n_groups"],
                ["枚数/品番", "imgs_per_part"],
                ["Epoch", "epochs"],
              ] as const
            ).map(([label, key]) => (
              <label key={key}>
                {label}
                <input
                  type="number"
                  value={form[key]}
                  onChange={(e) => setForm({ ...form, [key]: Number(e.target.value) })}
                />
              </label>
            ))}
          </div>
          <div className="btn-row">
            <button className="btn btn-primary" onClick={onGenerate} disabled={busy}>
              デモデータ生成＆学習
            </button>
            <button className="btn" onClick={onBuild} disabled={busy}>
              索引再構築
            </button>
          </div>
          <pre className="log">{log.join("\n")}</pre>
        </section>

        <section className="surface span-7">
          <div className="section-head">
            <div>
              <p className="eyebrow">Line Intelligence</p>
              <h3>現場イメージ</h3>
            </div>
          </div>
          <div className="asset-mosaic">
            {mosaic.map(([img, label]) => (
              <div className="mosaic-item" key={img}>
                <img src={asset(img)} alt={label} />
                <span>{label}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}
