import { useState } from "react";
import { useToast } from "@/app/useToast";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { controlClass, helpTextClass } from "@/components/ui/styles";
import { cn } from "@/lib/cn";
import type { BrokerInstruction, BrokerStatus } from "@/types/api";

interface BrokerCardProps {
  brokerKey: string;
  instruction: BrokerInstruction;
  status?: BrokerStatus;
  connecting: boolean;
  onConnect: (credentials: Record<string, string>) => void;
  onDisconnect: () => void;
}

export function BrokerCard(props: BrokerCardProps) {
  const { toast } = useToast();
  const [values, setValues] = useState<Record<string, string>>({});
  const connected = props.status?.connected ?? false;

  function submit() {
    const credentials = Object.fromEntries(
      props.instruction.fields.map((field) => [field, (values[field] ?? "").trim()]),
    );
    if (!Object.values(credentials).some(Boolean)) {
      toast("Enter credentials first");
      return;
    }
    props.onConnect(credentials);
  }

  return (
    <Card>
      <div className="flex items-baseline justify-between gap-2">
        <CardTitle>{props.instruction.name}</CardTitle>
        <span
          className={cn(
            "whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-extrabold",
            connected ? "bg-emerald-500/15 text-emerald-300" : "bg-yellow-400/15 text-yellow-300",
          )}
        >
          {connected ? "Connected" : "Not connected"}
        </span>
      </div>
      <p className={cn(helpTextClass, "my-2")}>
        Library:{" "}
        <code className="rounded bg-canvas px-1.5 py-0.5 text-slate-200">
          {props.instruction.library}
        </code>{" "}
        {props.status?.library_installed ? "(installed)" : "(run in terminal)"}
      </p>
      <ol className="list-decimal space-y-2 pl-5 text-xs leading-5 text-muted">
        {props.instruction.steps.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>
      <div className="mt-3 grid gap-2">
        {props.instruction.fields.map((field) => (
          <label key={field}>
            <span className="sr-only">{field}</span>
            <input
              className={controlClass}
              id={`${props.brokerKey}_${field}`}
              placeholder={field}
              value={values[field] ?? ""}
              onChange={(event) =>
                setValues((current) => ({ ...current, [field]: event.target.value }))
              }
            />
          </label>
        ))}
      </div>
      <div className="mt-3 flex flex-col gap-3 sm:flex-row">
        <Button onClick={submit} disabled={props.connecting}>
          Save & Connect
        </Button>
        <Button variant="secondary" onClick={props.onDisconnect}>
          Disconnect
        </Button>
      </div>
    </Card>
  );
}
