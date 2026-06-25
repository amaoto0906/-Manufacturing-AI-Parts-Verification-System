import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { partImg } from "../assets";
import { PartGallery } from "./PartGallery";
import type { Part, PartUpsert } from "../types";

interface EditForm {
  part_no: string;
  part_name: string;
  category: string;
  group_id: string;
  accept_threshold: string;
  margin_threshold: string;
  status: string;
  isNew: boolean;
}

const blank = (): EditForm => ({
  part_no: "",
  part_name: "",
  category: "",
  group_id: "",
  accept_threshold: "",
  margin_threshold: "",
  status: "active",
  isNew: true,
});

const toForm = (p: Part): EditForm => ({
  part_no: p.part_no,
  part_name: p.part_name ?? "",
  category: p.category ?? "",
  group_id: p.group_id?.toString() ?? "",
  accept_threshold: p.accept_threshold?.toString() ?? "",
  margin_threshold: p.margin_threshold?.toString() ?? "",
  status: p.status,
  isNew: false,
});

export function Parts() {
  const [parts, setParts] = useState<Part[]>([]);
  const [error, setError] = useState(false);
  const [edit, setEdit] = useState<EditForm | null>(null);
  const [msg, setMsg] = useState("");

  const load = useCallback(async () => {
    try {
      const { parts } = await api.parts(1000);
      setParts(parts);
      setError(false);
    } catch {
      setError(true);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const save = async () => {
    if (!edit) return;
    if (!edit.part_no.trim()) {
      setMsg("品番は必須です。");
      return;
    }
    const num = (s: string) => (s.trim() === "" ? null : Number(s));
    const body: PartUpsert = {
      part_no: edit.part_no.trim(),
      part_name: edit.part_name || null,
      category: edit.category || null,
      group_id: edit.group_id.trim() === "" ? null : Number(edit.group_id),
      status: edit.status,
      accept_threshold: num(edit.accept_threshold),
      margin_threshold: num(edit.margin_threshold),
    };
    try {
      await api.upsertPart(body);
      setMsg(`保存しました: ${body.part_no}`);
      setEdit(null);
      await load();
    } catch (e) {
      setMsg("保存失敗: " + (e as Error).message);
    }
  };

  return (
    <section className="surface">
      <div className="section-head">
        <div>
          <p className="eyebrow">Master Data</p>
          <h3>品番マスタ</h3>
        </div>
        <div className="filter-row">
          <button className="btn btn-primary btn-sm" onClick={() => setEdit(blank())}>
            ＋ 新規品番
          </button>
          <button className="btn btn-sm" onClick={load}>
            再読込
          </button>
        </div>
      </div>

      {edit && (
        <div className="edit-panel">
          <div className="edit-grid">
            <label>
              品番
              <input
                value={edit.part_no}
                disabled={!edit.isNew}
                onChange={(e) => setEdit({ ...edit, part_no: e.target.value })}
              />
            </label>
            <label>
              名称
              <input value={edit.part_name} onChange={(e) => setEdit({ ...edit, part_name: e.target.value })} />
            </label>
            <label>
              カテゴリ
              <input value={edit.category} onChange={(e) => setEdit({ ...edit, category: e.target.value })} />
            </label>
            <label>
              類似グループ
              <input
                type="number"
                value={edit.group_id}
                onChange={(e) => setEdit({ ...edit, group_id: e.target.value })}
              />
            </label>
            <label>
              受理しきい値<small>（空=既定）</small>
              <input
                type="number"
                step={0.01}
                value={edit.accept_threshold}
                onChange={(e) => setEdit({ ...edit, accept_threshold: e.target.value })}
              />
            </label>
            <label>
              マージンしきい値<small>（空=既定）</small>
              <input
                type="number"
                step={0.01}
                value={edit.margin_threshold}
                onChange={(e) => setEdit({ ...edit, margin_threshold: e.target.value })}
              />
            </label>
            <label>
              状態
              <select value={edit.status} onChange={(e) => setEdit({ ...edit, status: e.target.value })}>
                <option value="active">active</option>
                <option value="retired">retired</option>
              </select>
            </label>
          </div>
          <div className="btn-row">
            <button className="btn btn-primary btn-sm" onClick={save}>
              保存
            </button>
            <button className="btn btn-sm" onClick={() => setEdit(null)}>
              キャンセル
            </button>
            {msg && <span className="stats-note" style={{ marginLeft: 8 }}>{msg}</span>}
          </div>
        </div>
      )}

      <PartGallery className="parts-visuals" labels={parts.slice(0, 5).map((p) => p.part_no)} />
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>画像</th>
              <th>品番</th>
              <th>名称</th>
              <th>カテゴリ</th>
              <th>類似Gr</th>
              <th>受理しきい値</th>
              <th>マージンしきい値</th>
              <th>状態</th>
              <th>編集</th>
            </tr>
          </thead>
          <tbody>
            {error && (
              <tr>
                <td colSpan={9} className="muted">
                  APIに接続すると品番マスタを表示します。
                </td>
              </tr>
            )}
            {!error &&
              parts.map((p, i) => (
                <tr key={p.part_no}>
                  <td>
                    <img className="part-thumb" src={partImg(i)} alt={p.part_no} />
                  </td>
                  <td>
                    <b>{p.part_no}</b>
                  </td>
                  <td>{p.part_name ?? "-"}</td>
                  <td>{p.category ?? "-"}</td>
                  <td>{p.group_id ?? "-"}</td>
                  <td>{p.accept_threshold ?? "（既定）"}</td>
                  <td>{p.margin_threshold ?? "（既定）"}</td>
                  <td>{p.status}</td>
                  <td>
                    <button className="btn btn-sm" onClick={() => setEdit(toForm(p))}>
                      編集
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
