import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/endpoints";
import { useToast } from "@/app/useToast";
import { Section } from "@/components/Section";
import type { BrokerInstruction, BrokerStatus } from "@/types/api";

const BROKER_KEYS = ["zerodha", "angelone"] as const;

export default function BrokersPage() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [holdings, setHoldings] = useState<string | null>(null);

  const instructionsQuery = useQuery({
    queryKey: ["brokers", "instructions"],
    queryFn: api.brokerInstructions,
  });
  const statusQuery = useQuery({
    queryKey: ["brokers", "status"],
    queryFn: api.brokerStatus,
  });

  const connectMutation = useMutation({
    mutationFn: api.brokerConnect,
    onSuccess: () => {
      toast("Saved. Status refreshed.");
      void queryClient.invalidateQueries({ queryKey: ["brokers"] });
    },
    onError: (e) => toast(e instanceof Error ? e.message : "Connect failed"),
  });

  const disconnectMutation = useMutation({
    mutationFn: api.brokerDisconnect,
    onSuccess: () => {
      toast("Disconnected");
      void queryClient.invalidateQueries({ queryKey: ["brokers"] });
    },
    onError: (e) => toast(e instanceof Error ? e.message : "Disconnect failed"),
  });

  const holdingsMutation = useMutation({
    mutationFn: api.brokerHoldings,
    onSuccess: (r) => setHoldings(JSON.stringify(r, null, 2)),
    onError: (e) => {
      setHoldings(null);
      toast(e instanceof Error ? e.message : "Failed to fetch holdings");
    },
  });

  if (instructionsQuery.isPending || statusQuery.isPending) {
    return (
      <div className="center">
        <span className="spinner" /> Loading…
      </div>
    );
  }

  const instructions = instructionsQuery.data ?? {};
  const status = statusQuery.data ?? {};

  return (
    <>
      <Section
        title="Broker APIs"
        sub="Optional — connect Zerodha or Angel One for live LTP and your holdings. Works fine without them (uses free data)."
      />

      {BROKER_KEYS.map((key) => (
        <BrokerCard
          key={key}
          brokerKey={key}
          instruction={
            instructions[key] ?? { name: key, library: "", steps: [], fields: [] }
          }
          status={status[key]}
          onConnect={(credentials) =>
            connectMutation.mutate({ broker: key, credentials })
          }
          onDisconnect={() => disconnectMutation.mutate(key)}
          connecting={connectMutation.isPending}
        />
      ))}

      <div className="card">
        <div style={{ fontWeight: 700, fontSize: 17, marginBottom: 8 }}>
          My holdings / positions
        </div>
        <button
          className="btn secondary"
          onClick={() => holdingsMutation.mutate()}
          disabled={holdingsMutation.isPending}
        >
          Fetch from connected broker
        </button>
        <div style={{ marginTop: 10 }}>
          {holdingsMutation.isPending && (
            <div className="center">
              <span className="spinner" />
            </div>
          )}
          {holdings !== null && !holdingsMutation.isPending && (
            <div
              className="card"
              style={{
                whiteSpace: "pre-wrap",
                fontSize: 12,
                maxHeight: 300,
                overflow: "auto",
              }}
            >
              {holdings}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function BrokerCard({
  brokerKey,
  instruction,
  status,
  onConnect,
  onDisconnect,
  connecting,
}: {
  brokerKey: string;
  instruction: BrokerInstruction;
  status: BrokerStatus | undefined;
  onConnect: (credentials: Record<string, string>) => void;
  onDisconnect: () => void;
  connecting: boolean;
}) {
  const { toast } = useToast();
  const [values, setValues] = useState<Record<string, string>>({});
  const connected = status?.connected ?? false;

  const submit = () => {
    const credentials: Record<string, string> = {};
    for (const field of instruction.fields) {
      credentials[field] = (values[field] ?? "").trim();
    }
    if (!Object.values(credentials).some(Boolean)) {
      toast("Enter credentials first");
      return;
    }
    onConnect(credentials);
  };

  return (
    <div className="card">
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          gap: 8,
        }}
      >
        <div style={{ fontWeight: 700, fontSize: 17 }}>{instruction.name}</div>
        <div
          style={{
            fontWeight: 800,
            fontSize: 12,
            padding: "4px 10px",
            borderRadius: 999,
            whiteSpace: "nowrap",
            background: connected ? "rgba(34,197,94,.15)" : "rgba(234,179,8,.15)",
            color: connected ? "var(--green)" : "var(--yellow)",
          }}
        >
          {connected ? "Connected" : "Not connected"}
        </div>
      </div>

      <div className="mini" style={{ margin: "8px 0" }}>
        Library: <code className="inline">{instruction.library}</code>{" "}
        {status?.library_installed ? "(installed)" : "(run in terminal)"}
      </div>

      <ol style={{ paddingLeft: 20 }} className="mini">
        {instruction.steps.map((step) => (
          <li key={step} style={{ margin: "8px 0" }}>
            {step}
          </li>
        ))}
      </ol>

      <div style={{ height: 8 }} />
      {instruction.fields.map((field) => (
        <input
          key={field}
          id={`${brokerKey}_${field}`}
          type="text"
          placeholder={field}
          style={{ marginBottom: 8 }}
          value={values[field] ?? ""}
          onChange={(e) => setValues((v) => ({ ...v, [field]: e.target.value }))}
        />
      ))}

      <div className="row">
        <button className="btn" onClick={submit} disabled={connecting}>
          Save & Connect
        </button>
        <button className="btn secondary" onClick={onDisconnect}>
          Disconnect
        </button>
      </div>
    </div>
  );
}
