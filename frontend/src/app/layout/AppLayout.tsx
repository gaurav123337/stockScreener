import { Suspense } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  BrainCircuit,
  CircleHelp,
  Download,
  LogIn,
  LogOut,
  MessageSquareHeart,
  ScanSearch,
  Settings,
  TrendingUp,
  UserRound,
  WalletCards,
  type LucideIcon,
} from "lucide-react";
import { usePwaInstall } from "@/app/hooks/usePwaInstall";
import { LoadingState } from "@/components/ui/Spinner";
import { useAuth } from "@/features/auth/auth-context";
import { cn } from "@/lib/cn";

const TABS: ReadonlyArray<{ to: string; icon: LucideIcon; label: string }> = [
  { to: "/recommend", icon: TrendingUp, label: "Recommend" },
  { to: "/scan", icon: ScanSearch, label: "Scan" },
  { to: "/train", icon: BrainCircuit, label: "Train" },
  { to: "/brokers", icon: WalletCards, label: "Brokers" },
  { to: "/settings", icon: Settings, label: "Settings" },
  { to: "/guide", icon: CircleHelp, label: "Guide" },
  { to: "/feedback", icon: MessageSquareHeart, label: "Feedback" },
];

function PrimaryNavigation({ className }: { className?: string }) {
  return (
    <nav className={className} aria-label="Primary navigation">
      {TABS.map(({ to, icon: Icon, label }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            cn(
              "flex min-w-0 items-center justify-center gap-1.5 rounded-lg px-2 py-2 text-xs font-semibold text-muted transition-colors hover:bg-slate-800 hover:text-ink md:justify-start md:px-3 md:py-2.5 md:text-sm",
              isActive && "bg-emerald-500/15 text-emerald-300",
            )
          }
        >
          <Icon className="size-5 shrink-0" aria-hidden />
          <span className="truncate">{label}</span>
        </NavLink>
      ))}
    </nav>
  );
}

export function AppLayout() {
  const { canInstall, promptInstall } = usePwaInstall();
  const { user, isLoggedIn, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/auth/login", { replace: true });
  }

  return (
    <div className="min-h-screen bg-canvas">
      <header className="sticky top-0 z-30 border-b border-border bg-canvas/95 px-4 pt-[calc(0.75rem+env(safe-area-inset-top))] pb-3 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3">
          <NavLink to="/recommend" className="flex min-w-0 items-center gap-2 font-bold text-ink">
            <img src="/icon.svg" alt="" className="size-8 shrink-0 rounded-lg" />
            <span className="truncate">stockScreener</span>
          </NavLink>
          <div className="flex items-center gap-2">
            {isLoggedIn && user && (
              <span
                className="hidden max-w-48 items-center gap-1.5 truncate text-sm text-muted sm:flex"
                title={`Signed in as ${user.username}`}
              >
                <UserRound className="size-4 shrink-0" aria-hidden />
                <span className="truncate">{user.display_name || user.username}</span>
              </span>
            )}
            {canInstall && (
              <button
                type="button"
                className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-border px-2.5 text-sm font-semibold text-ink hover:bg-surface-raised"
                onClick={promptInstall}
              >
                <Download className="size-4" aria-hidden />
                <span className="hidden sm:inline">Install</span>
              </button>
            )}
            {isLoggedIn ? (
              <button
                type="button"
                className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-border px-2.5 text-sm font-semibold text-ink hover:bg-surface-raised"
                onClick={handleLogout}
              >
                <LogOut className="size-4" aria-hidden />
                <span className="hidden sm:inline">Logout</span>
              </button>
            ) : (
              <NavLink
                to="/auth/login"
                className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-border px-2.5 text-sm font-semibold text-ink hover:bg-surface-raised"
              >
                <LogIn className="size-4" aria-hidden />
                <span className="hidden sm:inline">Sign in</span>
              </NavLink>
            )}
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-6xl md:grid-cols-[13rem_minmax(0,1fr)]">
        <aside className="hidden border-r border-border px-3 py-5 md:block">
          <PrimaryNavigation className="sticky top-24 grid gap-1" />
        </aside>
        <main className="min-w-0 px-4 pt-5 pb-28 sm:px-6 md:pb-10">
          <Suspense fallback={<LoadingState />}>
            <Outlet />
          </Suspense>
        </main>
      </div>

      <PrimaryNavigation className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-7 border-t border-border bg-canvas/95 px-1 pt-1 pb-[calc(0.25rem+env(safe-area-inset-bottom))] backdrop-blur md:hidden" />
    </div>
  );
}
