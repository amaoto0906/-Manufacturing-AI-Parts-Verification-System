import { useEffect, useRef, useState } from "react";
import { api, pct } from "../api";
import { asset } from "../assets";
import { PartGallery } from "./PartGallery";
import { CameraCapture } from "./CameraCapture";
import type { InspectResponse, Part } from "../types";

const ACTION_LABEL: Record<string, string> = {
  pass: "出荷可",
  block: "出荷停止",
  manual_check: "要確認",
  retake: "再撮影",
};

export function Inspect() {
  const [parts, setParts] = useState<Part[]>([]);
  const [samplePart, setSamplePart] = useState("");
  const [expected, setExpected] = useState("");
  const [runQuality, setRunQuality] = useState(true);
  const [identify, setIdentify] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [captureReady, setCaptureReady] = useState(false);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [result, setResult] = useState<InspectResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const blobRef = useRef<Blob | null>(null);

  useEffect(() => {
    api
      .parts(500)
      .then(({ parts }) => {
        setParts(parts);
        if (parts[0]) setSamplePart(parts[0].part_no);
      })
      .catch(() => setParts([]));
  }, []);

  const setPreview = (blob: Blob) => {
    blobRef.current = blob;
    setPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return URL.createObjectURL(blob);
    });
    setCaptureReady(true);
  };

  const onGetSample = async () => {
    if (!samplePart) return;
    try {
      setPreview(await api.sampleImage(samplePart));
      if (!identify && !expected) setExpected(samplePart);
    } catch (e) {
      alert("サンプル取得失敗: " + (e as Error).message);
    }
  };

  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) setPreview(f);
  };

  const onInspect = async () => {
    if (!blobRef.current) {
      alert("画像を選択してください。");
      return;
    }
    setBusy(true);
    try {
      setResult(await api.inspect(blobRef.current, identify ? "" : expected, runQuality));
    } catch (e) {
      alert("照合失敗: " + (e as Error).message);
    }
    setBusy(false);
  };

  return (
    <div className="inspection-layout">
      <section className="surface capture-surface">
        <div className="section-head">
          <div>
            <p className="eyebrow">Capture</p>
            <h3>撮影画像</h3>
          </div>
          <span className={`state-pill ${captureReady ? "ready" : "neutral"}`}>
            {captureReady ? "入力準備完了" : "未選択"}
          </span>
        </div>
        <div className="preview-wrap">
          {previewUrl ? (
            <img id="preview" src={previewUrl} alt="撮影画像プレビュー" style={{ display: "block" }} />
          ) : (
            <div className="preview-empty">
              <img src={asset("calibration-plate.png")} alt="校正プレート" />
              <span>画像未選択</span>
            </div>
          )}
          <div className="scan-line" aria-hidden="true"></div>
        </div>
        <div className="form-row">
          <label className="grow">
            サンプル部品（実際に流す部品）
            <select value={samplePart} onChange={(e) => setSamplePart(e.target.value)}>
              {parts.map((p) => (
                <option key={p.part_no} value={p.part_no}>
                  {p.part_no}
                  {p.group_id != null ? ` (Gr${p.group_id})` : ""}
                </option>
              ))}
            </select>
          </label>
          <button className="btn" onClick={onGetSample}>
            サンプル撮影取得
          </button>
        </div>
        <div className="form-row">
          <label className="grow file-field">
            またはファイルを選択
            <input type="file" accept="image/*" capture="environment" onChange={onFile} />
          </label>
          <button className="btn" onClick={() => setCameraOpen((v) => !v)}>
            {cameraOpen ? "カメラを閉じる" : "📷 カメラで撮影"}
          </button>
        </div>
        {cameraOpen && (
          <CameraCapture
            onCapture={(blob) => {
              setPreview(blob);
              setCameraOpen(false);
            }}
            onClose={() => setCameraOpen(false)}
          />
        )}
        <PartGallery labels={parts.slice(0, 5).map((p) => p.part_no)} />
      </section>

      <section className="surface inspect-surface">
        <div className="section-head">
          <div>
            <p className="eyebrow">Decision Gate</p>
            <h3>照合実行</h3>
          </div>
          <img className="head-thumb" src={asset("workflow-safety-gate.png")} alt="安全ゲート" />
        </div>
        <div className="form-row">
          <label className="grow">
            期待品番（作業指示）
            <select
              value={identify ? "" : expected}
              disabled={identify}
              onChange={(e) => setExpected(e.target.value)}
            >
              <option value="">（指定なし）</option>
              {parts.map((p) => (
                <option key={p.part_no} value={p.part_no}>
                  {p.part_no}
                  {p.group_id != null ? ` (Gr${p.group_id})` : ""}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label className="check">
          <input type="checkbox" checked={identify} onChange={(e) => setIdentify(e.target.checked)} /> 識別モード（期待品番なしで品番を推定）
        </label>
        <label className="check">
          <input type="checkbox" checked={runQuality} onChange={(e) => setRunQuality(e.target.checked)} /> 画質ゲートを有効化
        </label>
        <div className="btn-row">
          <button className="btn btn-primary btn-large" onClick={onInspect} disabled={busy}>
            {busy ? "照合中…" : "照合する"}
          </button>
        </div>

        {result && <ResultPanel r={result} />}
      </section>
    </div>
  );
}

function ResultPanel({ r }: { r: InspectResponse }) {
  const conf = (r.confidence * 100).toFixed(1);
  const q = r.quality ?? {};
  return (
    <div className="result">
      <div className="result-head">
        <span className={`badge ${r.result}`}>{r.result}</span>
        <span className="action">→ {ACTION_LABEL[r.action] ?? r.action}</span>
        <span className="muted">{r.processing_time_ms} ms</span>
      </div>
      <div className="result-body">
        <div className="kv">
          <span>判定品番</span>
          <b>{r.predicted_part_no ?? "—"}</b>
        </div>
        <div className="kv">
          <span>期待品番</span>
          <b>{r.expected_part_no ?? "（指定なし）"}</b>
        </div>
        <div className="kv">
          <span>信頼度</span>
          <div className="bar">
            <div className="bar-fill" style={{ width: `${conf}%` }}></div>
            <span>{conf}%</span>
          </div>
        </div>
        <div className="kv">
          <span>Top1-Top2 マージン</span>
          <b>{r.margin.toFixed(4)}</b>
        </div>
        <div className="reason">{r.reason}</div>
        <h4>上位候補</h4>
        <table className="mini">
          <thead>
            <tr>
              <th>順位</th>
              <th>品番</th>
              <th>類似度</th>
              <th>信頼度</th>
              <th>Gr</th>
            </tr>
          </thead>
          <tbody>
            {r.top_candidates.map((c, i) => (
              <tr key={c.part_no}>
                <td>{i + 1}</td>
                <td>{c.part_no}</td>
                <td>{c.score.toFixed(4)}</td>
                <td>{pct(c.confidence, 1)}</td>
                <td>{c.group_id ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <h4>画質</h4>
        <div className="quality">
          {q.metrics &&
            Object.entries(q.metrics).map(([k, v]) => (
              <span className="qpill" key={k}>
                {k}: {v}
              </span>
            ))}
          {(q.issues ?? []).map((i) => (
            <span className="qpill bad" key={i}>
              {i}
            </span>
          ))}
          {!q.metrics && !(q.issues ?? []).length && <span className="muted">画質チェック未実行</span>}
        </div>
      </div>
    </div>
  );
}
