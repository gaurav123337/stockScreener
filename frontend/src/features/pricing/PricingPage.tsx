import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/api/endpoints";
import { useAuth } from "@/features/auth/auth-context";
import { useEntitlements } from "@/features/pro/hooks/useEntitlements";
import { Section } from "@/components/Section";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { LoadingState } from "@/components/ui/Spinner";
import { Disclaimer } from "@/components/Disclaimer";
import { useToast } from "@/app/useToast";
import { queryClient } from "@/app/queryClient";
import { BadgeCheck, Check, Lock, ShieldCheck, Sparkles } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { BillingPlan, CheckoutSession } from "@/types/api";

function formatINR(amount: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);
}

export default function PricingPage() {
  const { isLoggedIn } = useAuth();
  const { isPro, entitlements } = useEntitlements();
  const { toast } = useToast();
  const navigate = useNavigate();
  const [activeCheckout, setActiveCheckout] = useState<CheckoutSession | null>(null);
  const [confirmedPlan, setConfirmedPlan] = useState<string | null>(null);

  const plansQuery = useQuery({
    queryKey: ["billing", "plans"],
    queryFn: api.billingPlans,
  });

  const checkoutMutation = useMutation({
    mutationFn: api.createCheckout,
    onSuccess: (session) => setActiveCheckout(session),
    onError: (e) => toast(e instanceof Error ? e.message : "Could not start checkout"),
  });

  const confirmMutation = useMutation({
    mutationFn: api.confirmCheckout,
    onSuccess: async (result) => {
      setActiveCheckout(null);
      setConfirmedPlan(result.plan_id);
      await queryClient.invalidateQueries({ queryKey: ["billing"] });
      await queryClient.invalidateQueries({ queryKey: ["auth"] });
    },
    onError: (e) => toast(e instanceof Error ? e.message : "Payment could not be confirmed"),
  });

  const plans = plansQuery.data?.plans ?? [];

  const beginCheckout = (plan: BillingPlan) => {
    if (!isLoggedIn) {
      navigate("/auth/register");
      return;
    }
    setConfirmedPlan(null);
    checkoutMutation.mutate(plan.id);
  };

  return (
    <>
      <Section
        title="Pricing"
        sub="Free forever for core research. Upgrade for depth — everything Free already has stays free."
      />

      {isPro && (
        <div className="mb-4 flex items-center gap-2 rounded-panel border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm font-semibold text-emerald-700 dark:text-emerald-300">
          <BadgeCheck className="size-5" aria-hidden />
          You are on the Pro tier
          {entitlements?.renews_at && (
            <span className="font-normal text-muted">
              · renews {new Date(entitlements.renews_at).toLocaleDateString()}
            </span>
          )}
        </div>
      )}

      {plansQuery.isPending ? (
        <LoadingState />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {plans.map((plan) => (
            <Card
              key={plan.id}
              className={
                plan.highlighted
                  ? "border-brand/60 bg-gradient-to-b from-brand/10 to-surface p-6"
                  : "p-6"
              }
            >
              <div className="flex items-center justify-between gap-2">
                <h2 className="text-lg font-bold text-ink">{plan.name}</h2>
                {plan.highlighted && (
                  <span className="rounded-full bg-brand/20 px-2.5 py-0.5 text-xs font-bold uppercase tracking-wide text-brand">
                    Best value
                  </span>
                )}
              </div>
              <p className="mt-1 text-sm text-muted">{plan.description}</p>
              <div className="mt-4 flex items-baseline gap-2">
                <span className="text-3xl font-extrabold tracking-tight text-ink">
                  {formatINR(plan.price_inr)}
                </span>
                <span className="text-sm text-muted">
                  / {plan.interval === "month" ? "month" : "year"}
                </span>
              </div>
              <p className="text-xs text-muted">
                ≈ ${plan.price_usd} USD · {plan.currency}
              </p>
              <ul className="mt-4 space-y-2">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-2 text-sm text-ink">
                    <Check className="mt-0.5 size-4 shrink-0 text-emerald-600" aria-hidden />
                    {feature}
                  </li>
                ))}
              </ul>
              <Button
                className="mt-5"
                variant={plan.highlighted ? "primary" : "secondary"}
                onClick={() => beginCheckout(plan)}
              >
                {isLoggedIn ? "Start checkout" : "Sign up to upgrade"}
              </Button>
            </Card>
          ))}
        </div>
      )}

      {activeCheckout && (
        <Card className="mt-4 border-focus/50 bg-blue-500/5 p-6">
          <div className="flex items-start gap-3">
            <Lock className="mt-1 size-5 shrink-0 text-focus" aria-hidden />
            <div className="min-w-0 flex-1">
              <h3 className="font-bold text-ink">Sandbox checkout</h3>
              <p className="mt-1 text-sm leading-6 text-muted">
                No real payment runs in the preview environment — this simulates a
                payment provider so the full upgrade flow can be tested. In
                production, a real gateway (e.g. Razorpay) replaces this step.
              </p>
              <p className="mt-2 break-all text-xs text-muted">
                Session: <span className="font-mono">{activeCheckout.session_id}</span>
              </p>
              <Button
                className="mt-4 sm:w-auto"
                disabled={confirmMutation.isPending}
                onClick={() => confirmMutation.mutate(activeCheckout.session_id)}
              >
                <ShieldCheck className="size-4" aria-hidden />
                Confirm {formatINR(activeCheckout.amount_inr ?? 0)} payment (simulated)
              </Button>
            </div>
          </div>
        </Card>
      )}

      {confirmedPlan && !activeCheckout && (
        <Card className="mt-4 border-emerald-500/40 bg-emerald-500/10 p-6">
          <div className="flex items-start gap-3">
            <Sparkles className="mt-1 size-5 shrink-0 text-emerald-600" aria-hidden />
            <div>
              <h3 className="font-bold text-ink">Welcome to Pro</h3>
              <p className="mt-1 text-sm leading-6 text-muted">
                Your upgrade is live. Explore saved screens, portfolio analytics and
                strategy backtests.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button className="sm:w-auto" onClick={() => navigate("/pro")}>
                  Explore Pro
                </Button>
                <Button
                  variant="secondary"
                  className="sm:w-auto"
                  onClick={() => navigate("/recommend")}
                >
                  Continue research
                </Button>
              </div>
            </div>
          </div>
        </Card>
      )}

      <Disclaimer compliance={undefined} />
    </>
  );
}
