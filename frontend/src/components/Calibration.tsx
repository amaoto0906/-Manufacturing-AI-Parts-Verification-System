import { useState } from "react";
import { api } from "../api";
import { asset } from "../assets";
import type { CalibrateResult } from "../types";

export function Calibration() {
  const [res, setRes] = useState<CalibrateResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const run = async (save: boolean) => {
    setBusy(true);
    setMsg(save ? "導出して適用中…" : "導出中…");
    try {
      const r = await api.calibrateQuality(save);
      setRes(r);
      setMsg(save ? "保存・適用しました（MatchEngine に反映済み）。" : "導出しました（未適用）。");
    } catch (e) {
      setMsg("エラー: " + (e as Error).message);
    }
    setBusy(false);
  };

  const reset = async () => {
    setBusy(true);
    try {
      const r = await api.resetQuality();
      setMsg(r.reset ? "既定しきい値に戻しました。" : "適用中のキャリブレーションはありません。");
      setRes(null);
    } catch (e) {
      setMsg("エラー: " + (e as Error).message);
    }
    setBusy(false);
  };

  const val = res?.report.validation;

  return (
    <>
      <section className="surface history-hero">
        <img src={asset("calibration-plate.png")} alt="校正プレート" />
        <div className="section-head">
          <div>
            <p className="eyebrow">Quality Gate Calibration</p>
            <h3>画質しきい値の自動キャリブレーション</h3>
          </div>
          <div className="filter-row">
            <button className="btn btn-sm" onClick={() => run(false)} disabled={busy}>
              導出（試算）
            </button>
            <button className="btn btn-primary btn-sm" onClick={() => run(true)} disabled={busy}>
              適用して保存
            </button>
            <button className="btn btn-sm" onClick={reset} disabled={busy}>
              既定に戻す
            </button>
          </div>
        </div>
        <p className="muted" style={{ margin: 0 }}>
          現データセットから良品・不良品（ピンボケ／露出／反射／位置ズレ）を合成し、良品が通過し不良が弾かれる
          しきい値を自動導出します。実運用では現場の実画像で実施します。
        </p>
      </section>

      {msg && <div className="surface info-banner">{msg}</div>}

      {res && (
        <div className="dashboard-grid">
          <section className="surface span-5">
            <div className="section-head">
              <div>
                <p className="eyebrow">Validation</p>
                <h3>検証結果</h3>
              </div>
            </div>
            <div className="kpi-grid">
              <div className="kpi kpi-good">
                <div className="kpi-v">{val ? (val.good_reject_rate * 100).toFixed(1) + "%" : "-"}</div>
                <div className="kpi-l">良品の誤棄却率</div>
                <div className="kpi-hint">低いほど良い</div>
              </div>
              <div className="kpi kpi-good">
                <div className="kpi-v">{val && val.bad_reject_rate != null ? (val.bad_reject_rate * 100).toFixed(0) + "%" : "-"}</div>
                <div className="kpi-l">不良の棄却率</div>
                <div className="kpi-hint">高いほど良い</div>
              </div>
              <div className="kpi">
                <div className="kpi-v">{res.report.n_good}</div>
                <div className="kpi-l">良品サンプル</div>
              </div>
              <div className="kpi">
                <div className="kpi-v">{res.report.n_bad}</div>
                <div className="kpi-l">不良サンプル</div>
              </div>
            </div>
          </section>

          <section className="surface span-7">
            <div className="section-head">
              <div>
                <p className="eyebrow">Recommended</p>
                <h3>推奨しきい値</h3>
              </div>
            </div>
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>しきい値キー</th>
                    <th>推奨値</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(res.recommended).map(([k, v]) => (
                    <tr key={k}>
                      <td>
                        <b>{k}</b>
                      </td>
                      <td>{v.toFixed(6)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}
    </>
  );
}
