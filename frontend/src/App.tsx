import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import type { Info } from "./types";
import { Sidebar, Tabs, TABS, type TabId } from "./components/Nav";
import { Topbar } from "./components/Topbar";
import { Dashboard } from "./components/Dashboard";
import { Inspect } from "./components/Inspect";
import { Parts } from "./components/Parts";
import { History } from "./components/History";
import { Report } from "./components/Report";
import { Calibration } from "./components/Calibration";
import { Settings } from "./components/Settings";

export default function App() {
  const [tab, setTab] = useState<TabId>("dashboard");
  const [info, setInfo] = useState<Info | null>(null);
  const [offline, setOffline] = useState(false);

  const refreshInfo = useCallback(async () => {
    try {
      setInfo(await api.info());
      setOffline(false);
    } catch {
      setInfo(null);
      setOffline(true);
    }
  }, []);

  useEffect(() => {
    refreshInfo();
  }, [refreshInfo]);

  return (
    <div className="app-shell">
      <Sidebar active={tab} onSelect={setTab} />
      <div className="workspace">
        <Topbar info={info} offline={offline} />
        <Tabs active={tab} onSelect={setTab} />
        <main>
          <section className={`panel${tab === "dashboard" ? " active" : ""}`}>
            {tab === "dashboard" && <Dashboard info={info} offline={offline} onRefresh={refreshInfo} />}
          </section>
          <section className={`panel${tab === "inspect" ? " active" : ""}`}>
            {tab === "inspect" && <Inspect />}
          </section>
          <section className={`panel${tab === "parts" ? " active" : ""}`}>
            {tab === "parts" && <Parts />}
          </section>
          <section className={`panel${tab === "history" ? " active" : ""}`}>
            {tab === "history" && <History />}
          </section>
          <section className={`panel${tab === "report" ? " active" : ""}`}>
            {tab === "report" && <Report />}
          </section>
          <section className={`panel${tab === "calibration" ? " active" : ""}`}>
            {tab === "calibration" && <Calibration />}
          </section>
          <section className={`panel${tab === "settings" ? " active" : ""}`}>
            {tab === "settings" && <Settings />}
          </section>
        </main>
        <footer>
          部品照合システム v0.1.0 / DINOv2・CNN・Metric Learning・Vector Search・Safety Gate
        </footer>
      </div>
    </div>
  );
}

export { TABS };
