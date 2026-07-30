import { api } from "@/api/endpoints";
import { useToast } from "@/app/useToast";
import { Card } from "@/components/ui/Card";
import { controlClass } from "@/components/ui/styles";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Badge, PageHeader, QueryState } from "./shared";
import { formatDate, tableClass } from "./table-utils";

export default function FeedbackOpsPage() {
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [priority, setPriority] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { toast } = useToast();
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["admin", "feedback", status, priority, search],
    queryFn: () => {
      const params = new URLSearchParams();
      if (status) params.set("status", status);
      if (priority) params.set("priority", priority);
      if (search) params.set("search", search);
      return api.adminFeedback(params.toString());
    },
  });
  const detail = useQuery({
    queryKey: ["admin", "feedback", selectedId],
    queryFn: () => api.adminFeedbackDetail(selectedId || ""),
    enabled: Boolean(selectedId),
  });
  const mutation = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Record<string, unknown> }) =>
      api.updateAdminFeedback(id, patch),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["admin"] });
      toast("Feedback workflow updated");
    },
  });
  function update(id: string, key: string, value: string) {
    const reason = window.prompt("Reason for this workflow change:");
    if (reason?.trim()) mutation.mutate({ id, patch: { [key]: value, reason: reason.trim() } });
  }
  return (
    <>
      <PageHeader
        title="Feedback operations"
        description="Triage tester reports and maintain an accountable resolution workflow."
        actions={<span className="text-sm text-muted">{query.data?.total ?? 0} reports</span>}
      />
      <div className="mb-4 grid gap-2 sm:grid-cols-[minmax(0,1fr)_12rem_12rem]">
        <input className={controlClass} value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search feedback or reporter" />
        <select className={controlClass} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          {["new", "triaged", "planned", "in_progress", "resolved", "closed"].map((item) => <option key={item}>{item}</option>)}
        </select>
        <select className={controlClass} value={priority} onChange={(e) => setPriority(e.target.value)}>
          <option value="">All priorities</option>
          {["low", "medium", "high", "critical"].map((item) => <option key={item}>{item}</option>)}
        </select>
      </div>
      <QueryState loading={query.isLoading} error={query.error}>
        {query.data && (
          <Card className="overflow-hidden p-0">
            <div className="overflow-x-auto">
              <table className={tableClass}>
                <thead>
                  <tr>
                    <th>Feedback</th>
                    <th>Reporter</th>
                    <th>Priority</th>
                    <th>Status</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {query.data.items.map((item) => (
                    <tr key={item.feedback_id} onClick={() => setSelectedId(item.feedback_id)} className="cursor-pointer">
                      <td className="max-w-md">
                        <strong>{item.title}</strong>
                        <p className="mt-1 line-clamp-2 text-xs text-muted">{item.plain_text}</p>
                      </td>
                      <td>{item.username}</td>
                      <td>
                        <select
                          aria-label={`Priority for ${item.title}`}
                          className={`${controlClass} min-h-9 py-1`}
                          value={item.priority}
                          onChange={(e) => update(item.feedback_id, "priority", e.target.value)}
                        >
                          <option>low</option>
                          <option>medium</option>
                          <option>high</option>
                          <option>critical</option>
                        </select>
                      </td>
                      <td>
                        <select
                          aria-label={`Status for ${item.title}`}
                          className={`${controlClass} min-h-9 py-1`}
                          value={item.status}
                          onChange={(e) => update(item.feedback_id, "status", e.target.value)}
                        >
                          <option>new</option>
                          <option>triaged</option>
                          <option>planned</option>
                          <option>in_progress</option>
                          <option>resolved</option>
                          <option>closed</option>
                        </select>
                      </td>
                      <td>
                        <Badge>{formatDate(item.created_at)}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </QueryState>
      {selectedId && (
        <Card className="mt-4">
          <div className="flex items-start justify-between gap-4">
            <div><h2 className="font-bold">Feedback activity</h2><p className="text-sm text-muted">Workflow history and internal notes.</p></div>
            <button className="text-sm text-muted underline" onClick={() => setSelectedId(null)}>Close</button>
          </div>
          <QueryState loading={detail.isLoading} error={detail.error}>
            {detail.data && <div className="mt-4 grid gap-3">
              <p className="text-sm"><strong>{detail.data.feedback.title}</strong> — {detail.data.feedback.plain_text}</p>
              {detail.data.events.length === 0 ? <p className="text-sm text-muted">No workflow events yet.</p> : detail.data.events.map((event) => (
                <div key={event.event_id} className="rounded-xl border border-border p-3 text-sm">
                  <div className="flex justify-between gap-4"><strong>{event.event_type}</strong><span className="text-muted">{formatDate(event.created_at)}</span></div>
                  <p className="mt-1">{event.reason}</p>{event.note && <p className="mt-1 text-muted">Internal note: {event.note}</p>}
                </div>
              ))}
            </div>}
          </QueryState>
        </Card>
      )}
    </>
  );
}
