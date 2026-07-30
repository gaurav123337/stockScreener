import { api } from "@/api/endpoints";
import { Card } from "@/components/ui/Card";
import { useQuery } from "@tanstack/react-query";
import { PageHeader, QueryState } from "./shared";
import { formatDate, tableClass } from "./table-utils";

export default function AuditPage() {
  const query = useQuery({ queryKey: ["admin", "audit"], queryFn: api.adminAudit });
  return (
    <>
      <PageHeader
        title="Audit log"
        description="Immutable product-owner actions, reasons, targets, and field-level changes."
      />
      <QueryState loading={query.isLoading} error={query.error}>
        {query.data && (
          <Card className="overflow-hidden p-0">
            <div className="overflow-x-auto">
              <table className={tableClass}>
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Action</th>
                    <th>Target</th>
                    <th>Actor</th>
                    <th>Reason</th>
                    <th>Changes</th>
                  </tr>
                </thead>
                <tbody>
                  {query.data.items.map((item) => (
                    <tr key={item.event_id}>
                      <td>{formatDate(item.created_at)}</td>
                      <td className="font-semibold">{item.action}</td>
                      <td>
                        {item.target_type}:{item.target_id}
                      </td>
                      <td>{item.actor_id}</td>
                      <td className="max-w-xs">{item.reason}</td>
                      <td>
                        <code className="text-xs text-muted">{JSON.stringify(item.changes)}</code>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </QueryState>
    </>
  );
}
