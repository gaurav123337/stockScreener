import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/endpoints";
import { useToast } from "@/app/useToast";
import { Section } from "@/components/Section";
import { LoadingState } from "@/components/ui/Spinner";
import { BrokerCard } from "./components/BrokerCard";
import { HoldingsPanel } from "./components/HoldingsPanel";

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
    return <LoadingState />;
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
          instruction={instructions[key] ?? { name: key, library: "", steps: [], fields: [] }}
          status={status[key]}
          onConnect={(credentials) => connectMutation.mutate({ broker: key, credentials })}
          onDisconnect={() => disconnectMutation.mutate(key)}
          connecting={connectMutation.isPending}
        />
      ))}

      <HoldingsPanel
        holdings={holdings}
        loading={holdingsMutation.isPending}
        onFetch={() => holdingsMutation.mutate()}
      />
    </>
  );
}
