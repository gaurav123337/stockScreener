import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Sparkles } from "lucide-react";
import { useNavigate } from "react-router-dom";

export function UpgradePrompt({
  feature,
  description,
}: {
  feature: string;
  description: string;
}) {
  const navigate = useNavigate();
  return (
    <Card className="border-brand/40 bg-gradient-to-br from-brand/10 to-transparent p-6">
      <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-center">
        <div className="flex size-12 shrink-0 items-center justify-center rounded-panel bg-brand/20 text-brand">
          <Sparkles className="size-6" aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="text-lg font-bold text-ink">Pro feature</h2>
          <p className="mt-1 text-sm leading-6 text-muted">{description}</p>
          <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-brand">
            {feature}
          </p>
        </div>
        <Button
          className="sm:w-auto"
          onClick={() => navigate("/pricing")}
          aria-label="See Pro plans"
        >
          <Sparkles className="size-4" aria-hidden />
          Upgrade to Pro
        </Button>
      </div>
      <p className="mt-4 text-xs leading-5 text-muted">
        Everything on the Free tier stays free forever — screens, mutual-fund
        screener, risk profile, basket and the published track record. Pro adds
        research depth, never removes what you already have.
      </p>
    </Card>
  );
}
