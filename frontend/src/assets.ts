// 画像アセットのマッピング（public/assets/generated/ を base 付きで参照）
const BASE = import.meta.env.BASE_URL; // "/ui/"
export const asset = (name: string): string => `${BASE}assets/generated/${name}`;

export const workflowCards: Array<[string, string, string]> = [
  ["workflow-camera.png", "撮影", "治具・照明・カメラで入力画像を安定化"],
  ["workflow-quality.png", "画質ゲート", "ピンボケ、反射、位置ズレを先に停止"],
  ["workflow-embedding.png", "特徴抽出", "金属形状を照合向けベクトルへ変換"],
  ["vector-search.png", "ベクトル検索", "大量品番から近傍候補を高速取得"],
  ["workflow-safety-gate.png", "安全判定", "信頼度とマージンでOK/停止を制御"],
];

export const mosaic: Array<[string, string]> = [
  ["line-monitoring.png", "ライン監視"],
  ["operations-wallboard.png", "稼働分析"],
  ["lighting-design.png", "照明設計"],
  ["review-workflow.png", "レビュー"],
  ["edge-architecture.png", "エッジ構成"],
];

const partAssets = [
  "part-bracket.png",
  "part-flange.png",
  "part-clip.png",
  "part-reinforcement.png",
  "part-gusset.png",
  "workflow-trays.png",
  "calibration-plate.png",
  "data-generation.png",
  "metric-learning.png",
  "vector-search.png",
];
export const partImg = (i: number): string => asset(partAssets[i % partAssets.length]);
