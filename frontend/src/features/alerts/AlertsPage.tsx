import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/api/endpoints";
import { Section } from "@/components/Section";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { controlClass, labelClass, helpTextClass } from "@/components/ui/styles";
import { LoadingState } from "@/components/ui/Spinner";
import { useEntitlements } from "@/features/pro/hooks/useEntitlements";
import { UpgradePrompt } from "@/features/pro/components/UpgradePrompt";
import { usePushNotifications } from "@/app/hooks/usePushNotifications";
import { useToast } from "@/app/useToast";
import { queryClient } from "@/app/queryClient";
import { BellPlus, BellRing, Play, RefreshCw, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import type { AlertRuleType } from "@/types/api";

const RULE_LABELS: Record<AlertRuleType, string> = {
  price: "Stock price",
  screen_hit: "New screen match",
  mf_nav: "Mutual-fund NAV",
};

export default function AlertsPage() {
  const { toast } = useToast();
  const { isPro } = useEntitlements();
  const push = usePushNotifications();

  const [ruleType, setRuleType] = useState<AlertRuleType>("price");
  const [name, setName] = useState("");
  const [symbol, setSymbol] = useState("");
  const [schemeCode, setSchemeCode] = useState("");
  const [direction, setDirection] = useState<"above" | "below">("above");
  const [triggerValue, setTriggerValue] = useState("");
  const [screenId, setScreenId] = useState("");

  const alertsQuery = useQuery({ queryKey: ["alerts"], queryFn: api.listAlerts });
  const screensQuery = useQuery({ queryKey: ["pro", "screens"], queryFn: api.listSavedScreens });

  const createMutation = useMutation({
    mutationFn: api.createAlert,
    onSuccess: async () => {
      setName("");
      setSymbol("");
      setSchemeCode("");
      setTriggerValue("");
      setScreenId("");
      toast("Alert created");
      await queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
    onError: (e) => toast(e instanceof Error ? e.message : "Could not create alert"),
  });

  const deleteMutation = useMutation({
    mutationFn: api.deleteAlert,
    onSuccess: async () => {
      toast("Alert deleted");
      await queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
    onError: (e) => toast(e instanceof Error ? e.message : "Could not delete alert"),
  });

  const resetMutation = useMutation({
    mutationFn: api.resetAlert,
    onSuccess: async () => {
      toast("Alert re-armed");
      await queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
    onError: (e) => toast(e instanceof Error ? e.message : "Could not reset alert"),
  });

  const evaluateMutation = useMutation({
    mutationFn: api.evaluateAlerts,
    onSuccess: (result) => {
      if (result.fired.length > 0) {
        toast(`Fired ${result.fired.length} alert${result.fired.length > 1 ? "s" : ""}`);
      } else {
        toast("No alerts crossed their thresholds");
      }
      void queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
    onError: (e) => toast(e instanceof Error ? e.message : "Could not evaluate alerts"),
  });

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const value = parseFloat(triggerValue);
    if (Number.isNaN(value) || value < 0) {
      toast("Enter a valid threshold value");
      return;
    }
    createMutation.mutate({
      rule_type: ruleType,
      name: name.trim() || undefined,
      symbol: ruleType === "price" ? symbol.trim().toUpperCase() : undefined,
      scheme_code: ruleType === "mf_nav" ? schemeCode.trim() : undefined,
      direction,
      trigger_value: value,
      screen_id: ruleType === "screen_hit" ? screenId || undefined : undefined,
    });
  };

  const rules = alertsQuery.data?.rules ?? [];
  const screens = screensQuery.data?.screens ?? [];

  return (
    <>
      <Section
        title="Alerts"
        sub="Get notified when a price, screen or fund NAV crosses a level you care about. Each alert fires once and re-arms when you reset it."
      />

      {push.supported && (
        <Card className="mb-3 flex flex-wrap items-center justify-between gap-3 p-4">
          <div className="min-w-0">
            <p className="flex items-center gap-1.5 font-bold text-ink">
              <BellRing className="size-4 text-brand" aria-hidden />
              Browser notifications
            </p>
            <p className="mt-0.5 text-xs leading-5 text-muted">
              {push.permission === "granted"
                ? "Enabled — alert delivery can reach this device."
                : "Allow notifications to receive alerts as push messages on this device."}
              {push.error && <span className="text-danger"> {push.error}</span>}
            </p>
          </div>
          {push.permission === "granted" ? (
            <Button variant="secondary" className="sm:w-auto" onClick={() => void push.unsubscribe()}>
              Disable
            </Button>
          ) : (
            <Button
              variant="secondary"
              className="sm:w-auto"
              disabled={push.isSubscribing}
              onClick={() => {
                void push.subscribe().then((ok) => {
                  if (ok) toast("Notifications enabled");
                });
              }}
            >
              {push.isSubscribing ? "Enabling…" : "Enable"}
            </Button>
          )}
        </Card>
      )}

      {!isPro && (
        <>
          <UpgradePrompt
            feature="Price, screen and NAV alerts"
            description="Pro users set thresholds and get notified the moment they cross."
          />
          <div className="mt-4" />
        </>
      )}

      {isPro && (
        <Card className="p-5">
          <form onSubmit={handleSubmit} className="grid gap-3">
            <label className={labelClass}>
              Alert type
              <select
                className={controlClass}
                value={ruleType}
                onChange={(event) => setRuleType(event.target.value as AlertRuleType)}
              >
                {(Object.keys(RULE_LABELS) as AlertRuleType[]).map((type) => (
                  <option key={type} value={type}>
                    {RULE_LABELS[type]}
                  </option>
                ))}
              </select>
            </label>

            <label className={labelClass}>
              Name
              <input
                className={controlClass}
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="e.g. RELIANCE breaks 3000"
              />
            </label>

            {ruleType === "price" && (
              <label className={labelClass}>
                Symbol
                <input
                  className={controlClass}
                  value={symbol}
                  onChange={(event) => setSymbol(event.target.value)}
                  placeholder="e.g. RELIANCE"
                  required
                />
              </label>
            )}

            {ruleType === "mf_nav" && (
              <label className={labelClass}>
                Scheme code
                <input
                  className={controlClass}
                  value={schemeCode}
                  onChange={(event) => setSchemeCode(event.target.value)}
                  placeholder="e.g. 119598 (Nifty 50 index fund)"
                  required
                />
              </label>
            )}

            {ruleType === "screen_hit" && (
              <label className={labelClass}>
                Saved screen
                <select
                  className={controlClass}
                  value={screenId}
                  onChange={(event) => setScreenId(event.target.value)}
                  required
                >
                  <option value="">Select a screen…</option>
                  {screens.map((screen) => (
                    <option key={screen.screen_id} value={screen.screen_id}>
                      {screen.name}
                    </option>
                  ))}
                </select>
                <span className={helpTextClass}>
                  Fires when a screen run finds at least the threshold number of new matches.
                </span>
              </label>
            )}

            <div className="grid gap-3 sm:grid-cols-2">
              <label className={labelClass}>
                Direction
                <select
                  className={controlClass}
                  value={direction}
                  onChange={(event) => setDirection(event.target.value as "above" | "below")}
                >
                  <option value="above">Crosses above</option>
                  <option value="below">Crosses below</option>
                </select>
              </label>
              <label className={labelClass}>
                {ruleType === "screen_hit" ? "Minimum new matches" : "Threshold value"}
                <input
                  className={controlClass}
                  type="number"
                  step="any"
                  min="0"
                  value={triggerValue}
                  onChange={(event) => setTriggerValue(event.target.value)}
                  placeholder={ruleType === "screen_hit" ? "1" : "3000"}
                  required
                />
              </label>
            </div>

            <Button className="sm:w-auto" disabled={createMutation.isPending}>
              <BellPlus className="size-4" aria-hidden />
              Create alert
            </Button>
          </form>
        </Card>
      )}

      <Card className="flex flex-wrap items-center justify-between gap-3 border-brand/40 p-4">
        <p className="text-sm text-muted">
          Run every alert against the live market now. Fired alerts are one-shot until re-armed.
        </p>
        <Button
          variant="secondary"
          className="sm:w-auto"
          disabled={!isPro || rules.length === 0 || evaluateMutation.isPending}
          onClick={() => evaluateMutation.mutate([])}
        >
          <Play className="size-4" aria-hidden />
          Evaluate now
        </Button>
      </Card>

      {alertsQuery.isPending ? (
        <LoadingState />
      ) : rules.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted">
          No alerts yet. Create one above to get started.
        </p>
      ) : (
        <div className="space-y-3">
          {rules.map((rule) => (
            <Card key={rule.alert_id} className="p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="font-bold text-ink">{rule.name}</h3>
                  <p className="mt-0.5 text-xs text-muted">
                    {RULE_LABELS[rule.rule_type]} · {rule.direction}{" "}
                    {rule.trigger_value.toLocaleString("en-IN")}
                    {rule.symbol ? ` · ${rule.symbol}` : ""}
                    {rule.scheme_code ? ` · scheme ${rule.scheme_code}` : ""}
                  </p>
                  {rule.last_fired_at ? (
                    <p className="mt-1 text-xs font-semibold text-emerald-600">
                      Fired at {rule.last_value} · re-arms when you reset
                    </p>
                  ) : (
                    <p className="mt-1 text-xs text-muted">Armed — waiting for threshold.</p>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    className="sm:w-auto"
                    disabled={resetMutation.isPending}
                    onClick={() => resetMutation.mutate(rule.alert_id)}
                    title="Re-arm this alert"
                  >
                    <RefreshCw className="size-4" aria-hidden />
                    <span className="hidden sm:inline">Re-arm</span>
                  </Button>
                  <Button
                    variant="danger"
                    className="sm:w-auto"
                    disabled={deleteMutation.isPending}
                    onClick={() => deleteMutation.mutate(rule.alert_id)}
                    aria-label={`Delete ${rule.name}`}
                  >
                    <Trash2 className="size-4" aria-hidden />
                    <span className="hidden sm:inline">Delete</span>
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
