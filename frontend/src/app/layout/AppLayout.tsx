import { Suspense } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { usePwaInstall } from "@/app/hooks/usePwaInstall";
import styles from "./AppLayout.module.css";

const TABS = [
  { to: "/recommend", icon: "📈", label: "Recommend" },
  { to: "/scan", icon: "🔍", label: "Scan" },
  { to: "/train", icon: "🧠", label: "Train" },
  { to: "/brokers", icon: "💳", label: "Brokers" },
  { to: "/settings", icon: "⚙", label: "Settings" },
  { to: "/guide", icon: "❓", label: "Guide" },
] as const;

export function AppLayout() {
  const { canInstall, promptInstall } = usePwaInstall();

  return (
    <>
      <header className={styles.topbar}>
        <div className={styles.brand}>
          <img src="/icon.svg" alt="" className={styles.logo} />
          <span>stockScreener</span>
        </div>
        {canInstall && (
          <button className={styles.install} onClick={promptInstall}>
            Install
          </button>
        )}
      </header>

      <main className={styles.view}>
        <Suspense
          fallback={
            <div className="center">
              <span className="spinner" /> Loading…
            </div>
          }
        >
          <Outlet />
        </Suspense>
      </main>

      <nav className={styles.tabbar} aria-label="Primary">
        {TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            className={({ isActive }) => `${styles.tab}${isActive ? ` ${styles.active}` : ""}`}
          >
            <span className="ic" aria-hidden>
              {tab.icon}
            </span>
            <span className="lb">{tab.label}</span>
          </NavLink>
        ))}
      </nav>
    </>
  );
}
