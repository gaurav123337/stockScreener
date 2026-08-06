import { useFontSize } from "@/app/hooks/useFontSize";
import { usePwaInstall } from "@/app/hooks/usePwaInstall";
import { useTheme } from "@/app/hooks/useTheme";
import { LoadingState } from "@/components/ui/Spinner";
import { useAuth } from "@/features/auth/auth-context";
import { cn } from "@/lib/cn";
import {
  BarChart3,
  BrainCircuit,
  Briefcase,
  CircleHelp,
  Command,
  Download,
  Landmark,
  LogIn,
  LogOut,
  Menu,
  MessageSquareHeart,
  Minus,
  Moon,
  Plus,
  ScanSearch,
  Settings,
  Sparkles,
  Sun,
  TrendingUp,
  UserRound,
  WalletCards,
  type LucideIcon,
} from "lucide-react";
import { Suspense, useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

interface NavigationItem {
  to: string;
  icon: LucideIcon;
  label: string;
}

const PRIMARY_DESTINATIONS: ReadonlyArray<NavigationItem> = [
  { to: "/recommend", icon: TrendingUp, label: "Recommended" },
  { to: "/plan", icon: Sparkles, label: "My Plan" },
  { to: "/portfolio", icon: Briefcase, label: "My Portfolio" },
  { to: "/scan", icon: ScanSearch, label: "Scan" },
  { to: "/indian-market", icon: Landmark, label: "Indian Market" },
  { to: "/track-record", icon: BarChart3, label: "Track Record" },
  { to: "/train", icon: BrainCircuit, label: "Train" },
  { to: "/brokers", icon: WalletCards, label: "Broker" },
];

const SECONDARY_DESTINATIONS: ReadonlyArray<NavigationItem> = [
  { to: "/settings", icon: Settings, label: "Settings" },
  { to: "/guide", icon: CircleHelp, label: "Guide" },
  { to: "/feedback", icon: MessageSquareHeart, label: "Feedback" },
];

function PrimaryNavigation({ className }: { className?: string }) {
  return (
    <nav className={className} aria-label="Primary navigation">
      {PRIMARY_DESTINATIONS.map(({ to, icon: Icon, label }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            cn(
              "flex min-w-0 flex-col items-center justify-center gap-1 rounded-lg px-1 py-2 text-[11px] font-semibold text-muted transition-colors hover:bg-surface-raised hover:text-ink md:flex-row md:justify-start md:gap-2 md:px-3 md:py-2.5 md:text-sm",
              isActive && "bg-emerald-500/15 text-brand",
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

function SecondaryNavigation() {
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const location = useLocation();

  useEffect(() => setIsOpen(false), [location.pathname]);

  useEffect(() => {
    if (!isOpen) return;

    function handlePointerDown(event: PointerEvent) {
      if (!menuRef.current?.contains(event.target as Node)) setIsOpen(false);
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setIsOpen(false);
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  return (
    <div ref={menuRef} className="relative">
      <button
        type="button"
        className="inline-flex size-9 items-center justify-center rounded-lg border border-border text-ink transition-colors hover:bg-surface-raised"
        aria-label="Open more navigation"
        aria-controls="secondary-navigation"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((current) => !current)}
      >
        <Menu className="size-5" aria-hidden />
      </button>

      {isOpen && (
        <nav
          id="secondary-navigation"
          className="absolute right-0 top-11 z-40 grid min-w-48 gap-1 rounded-panel border border-border bg-surface p-2 shadow-panel"
          aria-label="More navigation"
        >
          {SECONDARY_DESTINATIONS.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-semibold text-muted transition-colors hover:bg-surface-raised hover:text-ink",
                  isActive && "bg-emerald-500/15 text-brand",
                )
              }
            >
              <Icon className="size-5" aria-hidden />
              {label}
            </NavLink>
          ))}
        </nav>
      )}
    </div>
  );
}

export function AppLayout() {
  const { canInstall, promptInstall } = usePwaInstall();
  const { user, isLoggedIn, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const { fontSize, increaseFontSize, decreaseFontSize, canIncrease, canDecrease } = useFontSize();
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
            <span className="hidden truncate sm:inline">stockScreener</span>
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
            {user?.role === "product_owner" && (
              <NavLink
                to="/control-center"
                className="inline-flex size-9 items-center justify-center rounded-lg border border-border text-ink hover:bg-surface-raised"
                aria-label="Open product owner control center"
                title="Control center"
              >
                <Command className="size-4" aria-hidden />
              </NavLink>
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
            <button
              type="button"
              className="inline-flex size-9 items-center justify-center rounded-lg border border-border text-ink transition-colors hover:bg-surface-raised"
              onClick={toggleTheme}
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
              title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
            >
              {theme === "dark" ? (
                <Sun className="size-4" aria-hidden />
              ) : (
                <Moon className="size-4" aria-hidden />
              )}
            </button>
            <div className="flex items-center gap-1" role="group" aria-label="Text size">
              <button
                type="button"
                className="inline-flex size-9 items-center justify-center rounded-lg border border-border text-ink transition-colors hover:bg-surface-raised disabled:cursor-not-allowed disabled:opacity-40"
                onClick={decreaseFontSize}
                disabled={!canDecrease}
                aria-label="Decrease text size"
                title="Decrease text size"
              >
                <Minus className="size-4" aria-hidden />
              </button>
              <span
                className="min-w-9 text-center text-xs font-semibold text-muted"
                aria-live="polite"
              >
                A {Math.round(fontSize)}%
              </span>
              <button
                type="button"
                className="inline-flex size-9 items-center justify-center rounded-lg border border-border text-ink transition-colors hover:bg-surface-raised disabled:cursor-not-allowed disabled:opacity-40"
                onClick={increaseFontSize}
                disabled={!canIncrease}
                aria-label="Increase text size"
                title="Increase text size"
              >
                <Plus className="size-4" aria-hidden />
              </button>
            </div>
            <SecondaryNavigation />
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

      <PrimaryNavigation className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-3 border-t border-border bg-canvas/95 px-1 pt-1 pb-[calc(0.25rem+env(safe-area-inset-bottom))] backdrop-blur md:hidden" />
    </div>
  );
}
