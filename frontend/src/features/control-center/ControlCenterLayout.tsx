import { useAuth } from "@/features/auth/auth-context";
import { cn } from "@/lib/cn";
import { Activity, ArrowLeft, LayoutDashboard, MessageSquare, Settings2, Users } from "lucide-react";
import { Navigate, NavLink, Outlet } from "react-router-dom";
import { Suspense } from "react";

const links = [
  { to: "/control-center", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/control-center/users", label: "Users", icon: Users },
  { to: "/control-center/feedback", label: "Feedback", icon: MessageSquare },
  { to: "/control-center/config", label: "Configuration", icon: Settings2 },
  { to: "/control-center/audit", label: "Audit log", icon: Activity },
];

export default function ControlCenterLayout() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/auth/login" replace />;
  if (user.role !== "product_owner") return <Navigate to="/recommend" replace />;

  return (
    <div className="min-h-screen bg-canvas">
      <header className="border-b border-border bg-surface px-4 py-3">
        <div className="mx-auto flex max-w-[1440px] items-center justify-between gap-4">
          <div className="flex min-w-0 items-center gap-3">
            <img src="/icon.svg" alt="" className="size-8 rounded-lg" />
            <div className="min-w-0">
              <p className="truncate text-sm font-bold">stockScreener Control Center</p>
              <p className="truncate text-xs text-muted">Product owner operations</p>
            </div>
          </div>
          <NavLink to="/recommend" className="inline-flex items-center gap-2 text-sm font-semibold text-muted hover:text-ink">
            <ArrowLeft className="size-4" aria-hidden /> Public app
          </NavLink>
        </div>
      </header>
      <div className="mx-auto grid max-w-[1440px] md:grid-cols-[14rem_minmax(0,1fr)]">
        <aside className="border-b border-border p-3 md:min-h-[calc(100vh-65px)] md:border-r md:border-b-0">
          <nav className="flex gap-1 overflow-x-auto md:sticky md:top-3 md:grid" aria-label="Control center navigation">
            {links.map(({ to, label, icon: Icon, end }) => (
              <NavLink key={to} to={to} end={end} className={({ isActive }) => cn(
                "flex shrink-0 items-center gap-2 rounded-lg px-3 py-2.5 text-sm font-semibold text-muted hover:bg-surface-raised hover:text-ink",
                isActive && "bg-emerald-500/15 text-brand",
              )}>
                <Icon className="size-4" aria-hidden />{label}
              </NavLink>
            ))}
          </nav>
        </aside>
        <main className="min-w-0 p-4 sm:p-6">
          <Suspense fallback={<div className="rounded-panel border border-border bg-surface p-6 text-sm text-muted">Loading control center…</div>}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}