import { useCallback, useEffect, useState } from "react";
import { api, pct } from "../api";
import { asset } from "../assets";
import type { HistoryLog, ResultKind } from "../types";

const FILTERS: Array<"" | ResultKind> = ["", "OK", "NG", "REVIEW", "RETAKE", "UNKNOWN"];

export function History() {
  const [logs, setLogs] = useState<HistoryLog[]>([]);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState(false);

  const load = useCallback(async (f: string) => {
    try {
      const { logs } = await api.history(100, f);
      setLogs(logs);
      setError(false);
    } catch {
      setError(true);
    }
  }, []);

  useEffect(() => {
    load(filter);
  }, [load, filter]);

  const confirm = async (l: HistoryLog) => {
    await api.feedback({
      inspection_log_id: l.id,
      feedback_type: "confirm",
      correct_part_no: l.predicted_part_no ?? "",
      created_by: "WEB",
    });
    alert("フィードバックを記録しました（再学習データに蓄積）。");
    load(filter);
  };

  const correct = async (l: HistoryLog) => {
    const pn = prompt("正しい品番を入力してください：");
    if (!pn) return;
    await api.feedback({
      inspection_log_id: l.id,
      feedback_type: "correct",
      correct_part_no: pn,
      created_by: "WEB",
    });
    alert("修正フィードバックを記録しました。");
    load(filter);
  };

  return (
    <section className="surface history-hero">
      <img src={asset("review-workflow.png")} alt="レビュー作業" />
      <div className="section-head">
        <div>
          <p className="eyebrow">Review Loop</p>
          <h3>照合履歴</h3>
        </div>
        <div className="filter-row">
          <select className="inline" value={filter} onChange={(e) => setFilter(e.target.value)}>
            {FILTERS.map((f) => (
              <option key={f || "all"} value={f}>
                {f || "すべて"}
              </option>
            ))}
          </select>
          <button className="btn btn-sm" onClick={() => load(filter)}>
            再読込
          </button>
        </div>
      </div>
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>ID</th>
              <th>判定</th>
              <th>期待</th>
              <th>判定品番</th>
              <th>信頼度</th>
              <th>理由</th>
              <th>時刻</th>
              <th>レビュー</th>
            </tr>
          </thead>
          <tbody>
            {(error || logs.length === 0) && (
              <tr>
                <td colSpan={8} className="muted">
                  {error ? "APIに接続すると照合履歴を表示します。" : "履歴はまだありません。"}
                </td>
              </tr>
            )}
            {!error &&
              logs.map((l) => (
                <tr key={l.id}>
                  <td>{l.id}</td>
                  <td>
                    <span className={`tag ${l.result}`}>{l.result}</span>
                  </td>
                  <td>{l.expected_part_no ?? "-"}</td>
                  <td>{l.predicted_part_no ?? "-"}</td>
                  <td>{l.confidence != null ? pct(l.confidence) : "-"}</td>
                  <td className="muted" style={{ maxWidth: 320 }}>
                    {l.reason ?? ""}
                  </td>
                  <td className="muted">{l.created_at}</td>
                  <td>
                    <button className="btn btn-sm" onClick={() => confirm(l)}>
                      正
                    </button>
                    <button className="btn btn-sm" onClick={() => correct(l)}>
                      誤
                    </button>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
