export type TabId =
  | "dashboard"
  | "inspect"
  | "parts"
  | "history"
  | "report"
  | "calibration"
  | "settings";

export const TABS: Array<{ id: TabId; icon: string; label: string }> = [
  { id: "dashboard", icon: "⌂", label: "ダッシュボード" },
  { id: "inspect", icon: "◎", label: "照合" },
  { id: "parts", icon: "▦", label: "品番マスタ" },
  { id: "history", icon: "◷", label: "履歴・レビュー" },
  { id: "report", icon: "◔", label: "精度レポート" },
  { id: "calibration", icon: "◐", label: "画質調整" },
  { id: "settings", icon: "⚙", label: "設定" },
];

interface NavProps {
  active: TabId;
  onSelect: (t: TabId) => void;
}

export function Sidebar({ active, onSelect }: NavProps) {
  return (
    <aside className="side-rail" aria-label="システムナビゲーション">
      <div className="brand-mark" aria-hidden="true">
        <span></span>
        <span></span>
        <span></span>
      </div>
      <nav className="rail-tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`rail-tab${active === t.id ? " active" : ""}`}
            title={t.label}
            aria-label={t.label}
            onClick={() => onSelect(t.id)}
          >
            {t.icon}
          </button>
        ))}
      </nav>
      <div className="rail-pulse" aria-hidden="true"></div>
    </aside>
  );
}

export function Tabs({ active, onSelect }: NavProps) {
  return (
    <nav className="tabs" aria-label="メインタブ">
      {TABS.map((t) => (
        <button
          key={t.id}
          className={`tab${active === t.id ? " active" : ""}`}
          onClick={() => onSelect(t.id)}
        >
          <span>{t.icon}</span>
          {t.label}
        </button>
      ))}
    </nav>
  );
}
