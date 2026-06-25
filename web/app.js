// 部品照合システム 管理コンソール
const API = "";
const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
let currentBlob = null;
let partsCache = [];

const assetBase = "./assets/generated/";
const assets = {
  workflow: [
    ["workflow-camera.png", "撮影", "治具・照明・カメラで入力画像を安定化"],
    ["workflow-quality.png", "画質ゲート", "ピンボケ、反射、位置ズレを先に停止"],
    ["workflow-embedding.png", "特徴抽出", "金属形状を照合向けベクトルへ変換"],
    ["vector-search.png", "ベクトル検索", "大量品番から近傍候補を高速取得"],
    ["workflow-safety-gate.png", "安全判定", "信頼度とマージンでOK/停止を制御"],
  ],
  mosaic: [
    ["line-monitoring.png", "ライン監視"], ["operations-wallboard.png", "稼働分析"],
    ["lighting-design.png", "照明設計"], ["review-workflow.png", "レビュー"],
    ["edge-architecture.png", "エッジ構成"],
  ],
  parts: [
    "part-bracket.png", "part-flange.png", "part-clip.png", "part-reinforcement.png", "part-gusset.png",
    "workflow-trays.png", "calibration-plate.png", "data-generation.png", "metric-learning.png", "vector-search.png",
  ],
};

async function api(path, opts) {
  const r = await fetch(API + path, opts);
  if (!r.ok) {
    let msg = r.status;
    try { msg = (await r.json()).detail || msg; } catch (e) {}
    throw new Error(msg);
  }
  return r;
}
const jget = (p) => api(p).then((r) => r.json());
const jpost = (p, body) => api(p, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body || {}),
}).then((r) => r.json());

function esc(v) {
  return String(v ?? "").replace(/[&<>'"]/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  }[c]));
}
function pct(v, digits = 0) { return v == null ? "-" : `${(v * 100).toFixed(digits)}%`; }
function asset(name) { return assetBase + name; }
function partImg(i) { return asset(assets.parts[i % assets.parts.length]); }

function bindTabs() {
  [...$$(".tab"), ...$$(".rail-tab")].forEach((t) => t.addEventListener("click", () => showTab(t.dataset.tab)));
}
function showTab(tab) {
  $$(".tab,.rail-tab").forEach((x) => x.classList.toggle("active", x.dataset.tab === tab));
  $$(".panel").forEach((x) => x.classList.toggle("active", x.id === tab));
  if (tab === "parts") loadParts();
  if (tab === "history") loadHistory();
}

function startClock() {
  const tick = () => {
    const el = $("#clock");
    if (el) el.textContent = new Intl.DateTimeFormat("ja-JP", {
      hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
    }).format(new Date());
  };
  tick();
  setInterval(tick, 1000);
}

function renderStaticVisuals() {
  const workflow = $("#workflow-strip");
  if (workflow) workflow.innerHTML = assets.workflow.map(([img, title, body], i) => `
    <article class="workflow-card" style="animation-delay:${i * 60}ms">
      <img src="${asset(img)}" alt="${esc(title)}">
      <div><b>${esc(title)}</b><span>${esc(body)}</span></div>
    </article>`).join("");

  const mosaic = $("#asset-mosaic");
  if (mosaic) mosaic.innerHTML = assets.mosaic.map(([img, label]) => `
    <div class="mosaic-item"><img src="${asset(img)}" alt="${esc(label)}"><span>${esc(label)}</span></div>`).join("");

  renderPartGallery("#part-gallery", ["PRS-00011", "PRS-00018", "PRS-00025", "PRS-00033", "PRS-00045"]);
  renderPartGallery("#parts-visuals", ["BRACKET", "FLANGE", "CLIP", "REINFORCE", "GUSSET"]);
}
function renderPartGallery(selector, labels) {
  const el = $(selector);
  if (!el) return;
  el.innerHTML = labels.map((label, i) => `
    <div class="part-tile" style="animation-delay:${i * 55}ms">
      <img src="${partImg(i)}" alt="${esc(label)}">
      <span>${esc(label)}</span>
    </div>`).join("");
}

async function loadDashboard() {
  const chip = $("#status-chip");
  try {
    const info = await jget("/api/v1/info");
    if (info.ready) { chip.innerHTML = "<span></span>稼働中・索引あり"; chip.className = "chip chip-ok"; }
    else { chip.innerHTML = "<span></span>索引未構築"; chip.className = "chip chip-warn"; }
    const th = info.thresholds || {};
    $("#info-cards").innerHTML = [
      card(info.ready ? "READY" : "未構築", "状態"),
      card(info.embedder?.backbone || "-", "バックボーン"),
      card(info.index_size ?? 0, "登録ベクトル"),
      card(`${info.embedder?.dim ?? "-"} 次元`, "埋め込み"),
      card(info.vector_backend || "-", "検索エンジン"),
      card(`${th.accept ?? "-"} / ${th.margin ?? "-"}`, "受理 / マージン"),
    ].join("");
    await loadStats();
    await loadSampleParts();
  } catch (e) {
    chip.innerHTML = "<span></span>API未接続";
    chip.className = "chip chip-gray";
    $("#info-cards").innerHTML = [
      card("OFFLINE", "状態"), card("UI READY", "コンソール"), card("20", "生成画像"),
      card("/ui", "配信先"), card("REST", "連携"), card("安全ゲート", "判定"),
    ].join("");
    renderEmptyStats("APIに接続すると照合ログを表示します");
  }
}
const card = (v, l) => `<div class="icard"><div class="v">${esc(v)}</div><div class="l">${esc(l)}</div></div>`;

async function loadStats() {
  try {
    const s = await jget("/api/v1/stats");
    const colors = { OK: "var(--ok)", NG: "var(--ng)", REVIEW: "var(--review)", RETAKE: "var(--retake)", UNKNOWN: "var(--unknown)" };
    const total = Object.values(s.by_result || {}).reduce((a, b) => a + b, 0) || 1;
    $("#result-breakdown").innerHTML = ["OK", "REVIEW", "NG", "RETAKE", "UNKNOWN"].map((k) => {
      const n = (s.by_result || {})[k] || 0;
      return `<div class="brow"><span class="name">${k}</span>
        <div class="track"><div class="fill" style="width:${(n / total * 100).toFixed(0)}%;background:${colors[k]}"></div></div>
        <span class="num">${n}</span></div>`;
    }).join("") + `<p class="stats-note">総照合 ${esc(s.n_inspections)} 件 / 平均 ${esc(s.avg_processing_ms ?? "-")} ms</p>`;
  } catch (e) { renderEmptyStats("履歴なし"); }
}
function renderEmptyStats(label) {
  $("#result-breakdown").innerHTML = ["OK", "REVIEW", "NG", "RETAKE", "UNKNOWN"].map((k) => `
    <div class="brow"><span class="name">${k}</span><div class="track"><div class="fill" style="width:0"></div></div><span class="num">0</span></div>`).join("") + `<p class="stats-note">${esc(label)}</p>`;
}

function bindAdmin() {
  $("#btn-refresh-dashboard")?.addEventListener("click", loadDashboard);
  $("#btn-generate")?.addEventListener("click", async () => {
    const btn = $("#btn-generate"); btn.disabled = true;
    log("デモデータ生成＋距離学習＋索引構築を実行中…");
    try {
      const r = await jpost("/api/v1/generate-demo", {
        n_parts: +$("#g-parts").value, n_groups: +$("#g-groups").value,
        imgs_per_part: +$("#g-imgs").value, epochs: +$("#g-epochs").value, seed: 42,
      });
      log(`完了: 部品 ${r.index.n_parts} / 画像 ${r.index.n_images} / 次元 ${r.index.dim} / 検索 ${r.index.backend}${r.index.train_summary ? " / 学習acc " + r.index.train_summary.train_acc.toFixed(3) : ""}`);
      await loadDashboard();
    } catch (e) { log("エラー: " + e.message); }
    btn.disabled = false;
  });
  $("#btn-build")?.addEventListener("click", async () => {
    log("索引再構築中…");
    try {
      const r = await jpost("/api/v1/build-index", { train: true, epochs: +$("#g-epochs").value });
      log("索引再構築 完了: " + JSON.stringify(r.summary.train_summary || r.summary));
      await loadDashboard();
    } catch (e) { log("エラー: " + e.message); }
  });
}
function log(m) {
  const el = $("#admin-log");
  if (el) el.textContent = "› " + m + "\n" + el.textContent;
}

async function loadSampleParts() {
  try {
    const { parts } = await jget("/api/v1/parts?limit=500");
    partsCache = parts || [];
    const opts = partsCache.map((p) => `<option value="${esc(p.part_no)}">${esc(p.part_no)}${p.group_id != null ? " (Gr" + esc(p.group_id) + ")" : ""}</option>`).join("");
    $("#sample-part").innerHTML = opts;
    $("#expected-part").innerHTML = `<option value="">（指定なし）</option>` + opts;
    renderPartGallery("#part-gallery", partsCache.slice(0, 5).map((p) => p.part_no));
  } catch (e) {}
}

function bindInspection() {
  $("#btn-sample")?.addEventListener("click", async () => {
    const pn = $("#sample-part").value;
    if (!pn) return;
    try {
      const r = await api(`/api/v1/sample-image?part_no=${encodeURIComponent(pn)}&seed=0`);
      currentBlob = await r.blob();
      showPreview(currentBlob);
      if (!$("#expected-part").value) $("#expected-part").value = pn;
    } catch (e) { alert("サンプル取得失敗: " + e.message); }
  });
  $("#file-input")?.addEventListener("change", (e) => {
    const f = e.target.files[0]; if (!f) return;
    currentBlob = f; showPreview(f);
  });
  $("#btn-inspect")?.addEventListener("click", async () => {
    if (!currentBlob) { alert("画像を選択してください。"); return; }
    const btn = $("#btn-inspect"); btn.disabled = true;
    const fd = new FormData();
    fd.append("file", currentBlob, "capture.png");
    const exp = $("#expected-part").value;
    if (exp) fd.append("expected_part_no", exp);
    fd.append("run_quality", $("#run-quality").checked);
    fd.append("operator_id", "WEB"); fd.append("line_id", "DEMO");
    try {
      const r = await api("/api/v1/inspect", { method: "POST", body: fd });
      renderResult(await r.json());
    } catch (e) { alert("照合失敗: " + e.message); }
    btn.disabled = false;
  });
}
function showPreview(blob) {
  const url = URL.createObjectURL(blob);
  $("#preview").src = url;
  $("#preview").style.display = "block";
  $("#preview-empty").style.display = "none";
  const state = $("#capture-state");
  state.textContent = "入力準備完了";
  state.className = "state-pill ready";
}

function renderResult(j) {
  $("#result").classList.remove("hidden");
  $("#result-badge").textContent = j.result;
  $("#result-badge").className = "badge " + j.result;
  const actMap = { pass: "出荷可", block: "出荷停止", manual_check: "要確認", retake: "再撮影" };
  $("#result-action").textContent = "→ " + (actMap[j.action] || j.action);
  $("#result-time").textContent = `${j.processing_time_ms} ms`;
  $("#r-pred").textContent = j.predicted_part_no || "—";
  $("#r-exp").textContent = j.expected_part_no || "（指定なし）";
  const conf = (j.confidence * 100).toFixed(1);
  $("#r-conf-bar").style.width = conf + "%";
  $("#r-conf-txt").textContent = conf + "%";
  $("#r-margin").textContent = j.margin.toFixed(4);
  $("#r-reason").textContent = j.reason;
  $("#r-cands").innerHTML = (j.top_candidates || []).map((c, i) =>
    `<tr><td>${i + 1}</td><td>${esc(c.part_no)}</td><td>${c.score.toFixed(4)}</td>
     <td>${pct(c.confidence, 1)}</td><td>${esc(c.group_id ?? "-")}</td></tr>`).join("");
  const q = j.quality || {};
  let qhtml = "";
  if (q.metrics) for (const [k, v] of Object.entries(q.metrics)) qhtml += `<span class="qpill">${esc(k)}: ${esc(v)}</span>`;
  (q.issues || []).forEach((i) => qhtml += `<span class="qpill bad">${esc(i)}</span>`);
  $("#r-quality").innerHTML = qhtml || `<span class="muted">画質チェック未実行</span>`;
  loadStats();
}

async function loadParts() {
  try {
    const { parts } = await jget("/api/v1/parts?limit=1000");
    partsCache = parts || [];
    $("#parts-body").innerHTML = partsCache.map((p, i) => `<tr>
      <td><img class="part-thumb" src="${partImg(i)}" alt="${esc(p.part_no)}"></td>
      <td><b>${esc(p.part_no)}</b></td><td>${esc(p.part_name ?? "-")}</td><td>${esc(p.category ?? "-")}</td>
      <td>${esc(p.group_id ?? "-")}</td><td>${esc(p.accept_threshold ?? "（既定）")}</td>
      <td>${esc(p.margin_threshold ?? "（既定）")}</td><td>${esc(p.status)}</td></tr>`).join("");
    renderPartGallery("#parts-visuals", partsCache.slice(0, 5).map((p) => p.part_no));
  } catch (e) {
    $("#parts-body").innerHTML = `<tr><td colspan="8" class="muted">APIに接続すると品番マスタを表示します。</td></tr>`;
  }
}

async function loadHistory() {
  try {
    const f = $("#hist-filter").value;
    const { logs } = await jget("/api/v1/history?limit=100" + (f ? "&result=" + encodeURIComponent(f) : ""));
    $("#hist-body").innerHTML = (logs || []).map((l) => `<tr>
      <td>${esc(l.id)}</td><td><span class="tag ${esc(l.result)}">${esc(l.result)}</span></td>
      <td>${esc(l.expected_part_no ?? "-")}</td><td>${esc(l.predicted_part_no ?? "-")}</td>
      <td>${l.confidence != null ? pct(l.confidence) : "-"}</td>
      <td class="muted" style="max-width:320px">${esc(l.reason ?? "")}</td>
      <td class="muted">${esc(l.created_at)}</td>
      <td>
        <button class="btn btn-sm" onclick="feedback(${Number(l.id)},'confirm','${esc(l.predicted_part_no ?? "")}')">正</button>
        <button class="btn btn-sm" onclick="feedbackCorrect(${Number(l.id)})">誤</button>
      </td></tr>`).join("") || `<tr><td colspan="8" class="muted">履歴はまだありません。</td></tr>`;
  } catch (e) {
    $("#hist-body").innerHTML = `<tr><td colspan="8" class="muted">APIに接続すると照合履歴を表示します。</td></tr>`;
  }
}

function bindReview() {
  $("#btn-reload-parts")?.addEventListener("click", loadParts);
  $("#btn-reload-hist")?.addEventListener("click", loadHistory);
  $("#hist-filter")?.addEventListener("change", loadHistory);
}
window.feedback = async (id, type, pn) => {
  await jpost("/api/v1/feedback", { inspection_log_id: id, feedback_type: type, correct_part_no: pn, created_by: "WEB" });
  alert("フィードバックを記録しました（再学習データに蓄積）。");
  loadHistory();
};
window.feedbackCorrect = async (id) => {
  const pn = prompt("正しい品番を入力してください：");
  if (!pn) return;
  await jpost("/api/v1/feedback", { inspection_log_id: id, feedback_type: "correct", correct_part_no: pn, created_by: "WEB" });
  alert("修正フィードバックを記録しました。");
  loadHistory();
};

bindTabs();
bindAdmin();
bindInspection();
bindReview();
startClock();
renderStaticVisuals();
loadDashboard();
