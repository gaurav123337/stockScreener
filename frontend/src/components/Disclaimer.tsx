import { ShieldAlert } from "lucide-react";
import type { ComplianceResponse } from "@/types/api";

/** Prominent trust/disclaimer panel (Phase-0 compliance framing).

 * Shown wherever scores or actions are displayed so the app never presents
 * rule-based output as advice or as a guarantee of returns.
 */
export function Disclaimer({
  compliance,
}: {
  compliance?: ComplianceResponse | null;
}) {
  const educational = compliance?.educational_note;
  const disclaimer = compliance?.disclaimer;
  const source = compliance?.data_source;

  if (!educational && !disclaimer) return null;

  return (
    <div
      role="note"
      className="mt-4 rounded-panel border border-warning/30 bg-warning/5 px-4 py-3 text-xs leading-5 text-muted"
    >
      <div className="flex items-start gap-2">
        <ShieldAlert className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden />
        <div className="space-y-1">
          {educational && <p>{educational}</p>}
          {disclaimer && <p>{disclaimer}</p>}
          {source && <p>{source}</p>}
        </div>
      </div>
    </div>
  );
}
