import { useEffect, useState } from "react";
import type { Info } from "../types";

function useClock(): string {
  const [t, setT] = useState("--:--:--");
  useEffect(() => {
    const fmt = new Intl.DateTimeFormat("ja-JP", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
    const tick = () => setT(fmt.format(new Date()));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);
  return t;
}

export function Topbar({ info, offline }: { info: Info | null; offline: boolean }) {
  const clock = useClock();
  let chipClass = "chip chip-gray";
  let chipText = "接続確認中";
  if (offline) {
    chipClass = "chip chip-gray";
    chipText = "API未接続";
  } else if (info) {
    if (info.ready) {
      chipClass = "chip chip-ok";
      chipText = "稼働中・索引あり";
    } else {
      chipClass = "chip chip-warn";
      chipText = "索引未構築";
    }
  }

  return (
    <header className="topbar">
      <div className="brand-copy">
        <p className="eyebrow">Manufacturing AI / Part Matching</p>
        <h1>部品照合システム</h1>
        <p className="sub">金属プレス部品の画像照合と出荷取り違え防止を行う現場コンソール</p>
      </div>
      <div className="topbar-actions">
        <div className="clock">{clock}</div>
        <div className={chipClass}>
          <span></span>
          {chipText}
        </div>
      </div>
    </header>
  );
}
