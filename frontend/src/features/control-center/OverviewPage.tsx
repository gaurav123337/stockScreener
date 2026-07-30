import { api } from "@/api/endpoints";
import { Card } from "@/components/ui/Card";
import { useQuery } from "@tanstack/react-query";
import { Badge, PageHeader, QueryState } from "./shared";
import { formatDate, tableClass } from "./table-utils";

export default function OverviewPage() {
  const query = useQuery({ queryKey: ["admin", "overview"], queryFn: api.adminOverview });
  return <><PageHeader title="Operations overview" description="Current account, verification, and feedback health." /><QueryState loading={query.isLoading} error={query.error}>{query.data && <div className="grid gap-5">
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {[ ["Registered users", query.data.users.total], ["Verified users", query.data.users.verified], ["Open feedback", query.data.feedback.open], ["Critical feedback", query.data.feedback.critical] ].map(([label, value]) => <Card key={label as string} className="rounded-lg"><p className="text-xs font-semibold uppercase text-muted">{label}</p><p className="mt-2 text-3xl font-bold">{value}</p></Card>)}
    </div>
    <Card className="overflow-hidden p-0"><div className="border-b border-border px-4 py-3"><h2 className="font-bold">Recent users</h2></div><div className="overflow-x-auto"><table className={tableClass}><thead><tr><th>User</th><th>Role</th><th>Status</th><th>Verified</th><th>Created</th></tr></thead><tbody>{query.data.recent_users.map((user) => <tr key={user.user_id}><td><strong>{user.display_name || user.username}</strong><div className="text-xs text-muted">{user.email || user.username}</div></td><td>{user.role}</td><td><Badge tone={user.status === "active" ? "good" : "bad"}>{user.status}</Badge></td><td>{user.email_verified_at ? "Yes" : "No"}</td><td>{formatDate(user.created_at)}</td></tr>)}</tbody></table></div></Card>
  </div>}</QueryState></>;
}