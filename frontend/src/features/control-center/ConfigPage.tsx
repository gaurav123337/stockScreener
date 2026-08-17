import { api } from "@/api/endpoints";
import { useToast } from "@/app/useToast";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { controlClass, labelClass } from "@/components/ui/styles";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { PageHeader, QueryState } from "./shared";
import { formatDate } from "./table-utils";

type DiffEntry = { key: string; before: unknown; after: unknown };

const PROVIDER_KEY_FIELDS = [
  { section: "fmp", label: "Financial Modeling Prep" },
  { section: "alphavantage", label: "Alpha Vantage" },
  { section: "finnhub", label: "Finnhub" },
];

export default function ConfigPage() {
  const query = useQuery({ queryKey: ["admin", "config"], queryFn: api.currentGlobalConfig });
  const history = useQuery({ queryKey: ["admin", "config", "history"], queryFn: api.globalConfigHistory });
  const [draft, setDraft] = useState("");
  const [policyDraft, setPolicyDraft] = useState("");
  const [reason, setReason] = useState("");
  const [diff, setDiff] = useState<DiffEntry[] | null>(null);
  const { toast } = useToast();
  const client = useQueryClient();

  useEffect(() => {
    if (query.data) {
      setDraft(JSON.stringify(query.data.values, null, 2));
      setPolicyDraft(JSON.stringify(query.data.policies, null, 2));
    }
  }, [query.data]);

  function readDraft(): Record<string, unknown> {
    try { return JSON.parse(draft) as Record<string, unknown>; } catch { return {}; }
  }
  function currentValue(key: string): string {
    const value = readDraft()[key];
    return typeof value === "string" ? value : "";
  }
  function currentBool(key: string): boolean {
    return Boolean(readDraft()[key]);
  }
  function patchDraft(key: string, value: string) {
    const patch = readDraft();
    patch[key] = value;
    setDraft(JSON.stringify(patch, null, 2));
    setDiff(null);
  }
  function nestedValue(section: string, key: string): string {
    const value = (readDraft()[section] as Record<string, unknown> | undefined)?.[key];
    return typeof value === "string" ? value : "";
  }
  function patchNested(section: string, key: string, value: string) {
    const patch = readDraft();
    const sub = { ...((patch[section] as Record<string, unknown>) ?? {}), [key]: value };
    patch[section] = sub;
    setDraft(JSON.stringify(patch, null, 2));
    setDiff(null);
  }
  function chainValue(): string {
    const value = readDraft().provider_chain;
    return Array.isArray(value) ? (value as string[]).join(", ") : "";
  }
  function patchChain(value: string) {
    const patch = readDraft();
    patch.provider_chain = value.split(",").map((part) => part.trim()).filter(Boolean);
    setDraft(JSON.stringify(patch, null, 2));
    setDiff(null);
  }

  const published = query.data?.values ?? {};
  const providerChanged =
    currentValue("market_data_provider") !== (published as Record<string, unknown>).market_data_provider ||
    currentValue("indian_market_provider") !== (published as Record<string, unknown>).indian_market_provider;

  const publish = useMutation({
    mutationFn: async () => {
      const patch = JSON.parse(draft) as Record<string, unknown>;
      const policies = JSON.parse(policyDraft) as Record<string, string>;
      const result = await api.diffGlobalConfig(patch);
      if (diff === null) {
        setDiff(result.changes);
        throw new Error("Review the generated diff, then publish again to confirm");
      }
      return api.publishGlobalConfig(patch, policies, reason, query.data?.version ?? 0);
    },
    onSuccess: (data) => {
      client.invalidateQueries({ queryKey: ["admin"] });
      setReason("");
      setDiff(null);
      toast(`Configuration version ${data.version} published`);
    },
    onError: (error) => toast(error instanceof Error ? error.message : "Configuration publication failed"),
  });

  const rollback = useMutation({
    mutationFn: ({ version, reason }: { version: number; reason: string }) => api.rollbackGlobalConfig(version, reason),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["admin"] });
      toast("Configuration rollback published as a new version");
    },
  });

  function requestRollback(version: number) {
    const rollbackReason = window.prompt(`Reason to roll back to version ${version}:`);
    if (rollbackReason?.trim()) rollback.mutate({ version, reason: rollbackReason.trim() });
  }

  return (
    <>
      <PageHeader
        title="Global configuration"
        description="Validate and publish versioned defaults applied across the product."
        actions={<span className="text-sm text-muted">Active version {query.data?.version ?? 0}</span>}
      />
      <QueryState loading={query.isLoading} error={query.error}>
        {query.data && (
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_20rem]">
            <div className="grid gap-4">
              <Card>
                <h2 className="font-bold">Market data providers</h2>
                <p className="mt-1 text-sm text-muted">
                  Pick the backend behind the screener and the Indian research workspace. Changes apply once you publish below.
                </p>
                <label className={`${labelClass} mt-4`}>
                  Core screener provider
                  <select
                    className={controlClass}
                    value={currentValue("market_data_provider") || "yahoo"}
                    onChange={(e) => patchDraft("market_data_provider", e.target.value)}
                  >
                    <option value="yahoo">Yahoo Finance</option>
                    <option value="indian_api">Indian API</option>
                    <option value="hybrid">Hybrid (Yahoo + Indian API fallback)</option>
                    <option value="fmp">Financial Modeling Prep</option>
                    <option value="alphavantage">Alpha Vantage</option>
                    <option value="finnhub">Finnhub</option>
                    <option value="chain">Failover chain (see provider_chain)</option>
                  </select>
                </label>
                <label className={`${labelClass} mt-4`}>
                  Failover chain (comma-separated, tried in order)
                  <input
                    className={controlClass}
                    value={chainValue()}
                    onChange={(e) => patchChain(e.target.value)}
                    placeholder="fmp, alphavantage, finnhub, yahoo"
                  />
                </label>
                <p className="mt-3 text-xs text-muted">
                  Chain members without a configured API key are skipped automatically.
                </p>
                <label className="mt-4 flex items-center gap-2 text-sm font-semibold">
                  <input
                    type="checkbox"
                    className="size-4 accent-brand"
                    checked={currentBool("show_data_source")}
                    onChange={(e) => patchDraft("show_data_source", String(e.target.checked))}
                  />
                  Show the active data source on every page
                </label>
                {PROVIDER_KEY_FIELDS.map(({ section, label }) => (
                  <label className={`${labelClass} mt-4`} key={section}>
                    {label} API key
                    <input
                      className={controlClass}
                      type="password"
                      value={nestedValue(section, "api_key")}
                      onChange={(e) => patchNested(section, "api_key", e.target.value)}
                      placeholder="paste your free-tier key"
                      autoComplete="off"
                    />
                  </label>
                ))}
                <label className={`${labelClass} mt-4`}>
                  Indian market workspace provider
                  <select
                    className={controlClass}
                    value={currentValue("indian_market_provider") || "indian_api"}
                    onChange={(e) => patchDraft("indian_market_provider", e.target.value)}
                  >
                    <option value="indian_api">Indian API</option>
                    <option value="yahoo">Yahoo Finance</option>
                  </select>
                </label>
                {providerChanged && (
                  <p className="mt-3 rounded-lg border border-accent/30 bg-accent/5 px-3 py-2 text-xs font-medium">
                    Unpublished provider change detected — publish below to make it live.
                  </p>
                )}
                <label className={`${labelClass} mt-4`}>
                  Required reason
                  <textarea
                    className={`${controlClass} min-h-24`}
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder="Why is this provider change being made?"
                  />
                </label>
                <Button
                  className="mt-4"
                  disabled={publish.isPending || reason.trim().length < 3}
                  onClick={() => publish.mutate()}
                >
                  {publish.isPending ? "Working..." : diff === null ? "Publish provider change" : "Confirm and publish"}
                </Button>
                {diff && diff.length > 0 && (
                  <div className="mt-4 rounded-xl border border-border p-3 text-xs">
                    <strong>{diff.length} changed settings</strong>
                    {diff.slice(0, 8).map((item) => (
                      <p key={item.key} className="mt-1 break-all">
                        {item.key}: {JSON.stringify(item.before)} → {JSON.stringify(item.after)}
                      </p>
                    ))}
                  </div>
                )}
              </Card>
              <Card>
                <label className={labelClass}>
                  Configuration JSON
                  <textarea
                    className={`${controlClass} min-h-[32rem] font-mono text-xs`}
                    value={draft}
                    onChange={(e) => { setDraft(e.target.value); setDiff(null); }}
                    spellCheck={false}
                  />
                </label>
              </Card>
              <Card>
                <label className={labelClass}>
                  Override policies JSON
                  <textarea
                    className={`${controlClass} min-h-48 font-mono text-xs`}
                    value={policyDraft}
                    onChange={(e) => { setPolicyDraft(e.target.value); setDiff(null); }}
                    spellCheck={false}
                  />
                </label>
                <p className="mt-2 text-xs text-muted">Use user_overridable or locked for registry paths.</p>
              </Card>
            </div>
            <div className="grid content-start gap-4">
              <Card>
                <h2 className="font-bold">Publish changes</h2>
                <p className="mt-1 text-sm text-muted">
                  Publication is validated, persisted, versioned, and written to the audit log.
                </p>
                <Button
                  className="mt-4"
                  disabled={publish.isPending || reason.trim().length < 3}
                  onClick={() => publish.mutate()}
                >
                  {publish.isPending ? "Working..." : diff === null ? "Validate and review diff" : "Confirm and publish"}
                </Button>
              </Card>
              <Card>
                <h2 className="font-bold">Version history</h2>
                <div className="mt-3 grid gap-2">
                  {history.data?.items.map((item) => (
                    <div key={item.version} className="rounded-xl border border-border p-3 text-sm">
                      <strong>Version {item.version}</strong>
                      <p className="text-xs text-muted">
                        {item.reason || "No reason"} · {formatDate(item.created_at)}
                      </p>
                      {item.version !== query.data?.version && (
                        <button className="mt-2 text-xs font-semibold underline" onClick={() => requestRollback(item.version)}>
                          Roll back to this version
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          </div>
        )}
      </QueryState>
    </>
  );
}
