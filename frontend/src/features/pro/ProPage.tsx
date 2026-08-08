import { useEntitlements } from "./hooks/useEntitlements";
import { UpgradePrompt } from "./components/UpgradePrompt";
import { Section } from "@/components/Section";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { LoadingState } from "@/components/ui/Spinner";
import { useNavigate } from "react-router-dom";
import {
  BellRing,
  Briefcase,
  FlaskConical,
  LineChart,
} from "lucide-react";

const PRO_FEATURES = [
  {
    to: "/pro/screens",
    icon: BellRing,
    title: "Saved screens & email alerts",
    description:
      "Persist any custom filter and re-run it against the live universe on demand. Pro adds email alerts when new matches appear.",
  },
  {
    to: "/pro/portfolio",
    icon: Briefcase,
    title: "Portfolio analytics",
    description:
      "Sector exposure, valuation mix, dividend-yield estimate, concentration and per-holding quality — computed from the same signal engine.",
  },
  {
    to: "/pro/backtest",
    icon: FlaskConical,
    title: "Strategy backtests",
    description:
      "Focused per-strategy walk-forward replays on the symbols you care about, with dated hit-rates vs the benchmark.",
  },
];

export default function ProPage() {
  const { isPro, isPending } = useEntitlements();
  const navigate = useNavigate();

  if (isPending) return <LoadingState>Checking your plan…</LoadingState>;

  return (
    <>
      <Section
        title="Pro research"
        sub="Deeper tools for serious research. The Free tier keeps every core screen — Pro adds depth, never removes what you already have."
      />

      {!isPro && (
        <UpgradePrompt
          feature="Pro research tools"
          description="Unlock saved screens with email alerts, portfolio analytics, and per-strategy deep backtests."
        />
      )}

      <div className="grid gap-4 md:grid-cols-3">
        {PRO_FEATURES.map(({ to, icon: Icon, title, description }) => (
          <Card key={to} className="flex flex-col p-5">
            <div className="flex size-11 items-center justify-center rounded-panel bg-brand/15 text-brand">
              <Icon className="size-5" aria-hidden />
            </div>
            <h2 className="mt-3 font-bold text-ink">{title}</h2>
            <p className="mt-1 flex-1 text-sm leading-6 text-muted">{description}</p>
            <Button
              className="mt-4 sm:w-auto"
              variant="secondary"
              onClick={() => navigate(to)}
            >
              <LineChart className="size-4" aria-hidden />
              Open
            </Button>
          </Card>
        ))}
      </div>
    </>
  );
}
