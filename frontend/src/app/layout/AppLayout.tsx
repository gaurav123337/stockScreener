import { Suspense } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { usePwaInstall } from "@/app/hooks/usePwaInstall";
import { useAuth } from "@/features/auth/auth-context";
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
  const { user, isLoggedIn, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/auth/login", { replace: true });
  }

  return (
    <>
      <header className={styles.topbar}>
        <div className={styles.brand}>
          <img src="/icon.svg" alt="" className={styles.logo} />
          <span>stockScreener</span>
        </div>
        <div className={styles.topbarActions}>
          {isLoggedIn && user && (
            <span className={styles.userBadge} title={`Signed in as ${user.username}`}>
              👤 {user.display_name || user.username}
            </span>
          )}
          {canInstall && (
            <button className={styles.install} onClick={promptInstall}>
              Install
            </button>
          )}
          {isLoggedIn ? (
            <button className={styles.authBtn} onClick={handleLogout}>
              Logout
            </button>
          ) : (
            <NavLink to="/auth/login" className={styles.authBtn}>
              Sign In
            </NavLink>
          )}
        </div>
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
