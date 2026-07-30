import { api } from "@/api/endpoints";
import { Card } from "@/components/ui/Card";
import type { AdminOverview } from "@/types/api";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge, PageHeader, QueryState } from "./shared";
import { formatDate, tableClass } from "./table-utils";

type Metric = { label: string; value: number; to: string; note?: string };
const labels: Record<string, string> = { under_7d: "Under 7 days", "7_to_30d": "7-30 days", over_30d: "Over 30 days", in_progress: "In progress" };
const displayLabel = (value: string) => labels[value] ?? value.replaceAll("_", " ");

function MetricCard({ metric }: { metric: Metric }) {
  return <Link to={metric.to} className="group rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"><Card className="h-full rounded-lg transition-colors group-hover:border-brand/50"><div className="flex items-start justify-between gap-3"><p className="text-xs font-semibold uppercase text-muted">{metric.label}</p><ArrowUpRight className="size-4 text-muted group-hover:text-brand" aria-hidden="true" /></div><p className="mt-2 text-3xl font-bold">{metric.value}</p>{metric.note && <p className="mt-1 text-xs text-muted">{metric.note}</p>}</Card></Link>;
}

function Breakdown({ heading, values, linkFor }: { heading: string; values: Record<string, number>; linkFor: (key: string) => string }) {
  return <Card><h2 className="font-bold">{heading}</h2><div className="mt-3 divide-y divide-border">{Object.entries(values).map(([key, value]) => <Link key={key} to={linkFor(key)} className="flex items-center justify-between gap-3 py-2 text-sm hover:text-brand"><span className="capitalize">{displayLabel(key)}</span><strong>{value}</strong></Link>)}</div></Card>;
}

function Dashboard({ data }: { data: AdminOverview }) {
  const metrics: Metric[] = [
    { label: "Registered users", value: data.users.total, to: "/control-center/users" },
    { label: "Verified users", value: data.users.verified, to: "/control-center/users?verified=true" },
    { label: "Active accounts", value: data.users.active, to: "/control-center/users?status=active" },
    { label: "New users - 7 days", value: data.users.new_7d, to: "/control-center/users?registered_within_days=7" },
    { label: "New users - 30 days", value: data.users.new_30d, to: "/control-center/users?registered_within_days=30" },
    { label: "Open feedback", value: data.feedback.open, to: "/control-center/feedback?status=open" },
    { label: "Critical feedback", value: data.feedback.critical, to: "/control-center/feedback?priority=critical" },
    { label: "Overdue feedback", value: data.feedback.overdue, to: "/control-center/feedback?age=overdue", note: "Open for 7+ days" },
  ];
  return <div className="grid gap-5">
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{metrics.map((metric) => <MetricCard key={metric.label} metric={metric} />)}</div>
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <Breakdown heading="Accounts by status" values={data.users.by_status} linkFor={(key) => `/control-center/users?status=${key}`} />
      <Breakdown heading="Email verification" values={data.users.by_verification} linkFor={(key) => `/control-center/users?verified=${key === "verified"}`} />
      <Breakdown heading="Feedback by status" values={data.feedback.by_status} linkFor={(key) => `/control-center/feedback?status=${key}`} />
      <Breakdown heading="Feedback by priority" values={data.feedback.by_priority} linkFor={(key) => `/control-center/feedback?priority=${key}`} />
      <Breakdown heading="Feedback by category" values={data.feedback.by_category} linkFor={(key) => `/control-center/feedback?category=${key}`} />
      <Breakdown heading="Feedback by age" values={data.feedback.by_age} linkFor={(key) => `/control-center/feedback?age=${key}`} />
      <Card className="md:col-span-2"><h2 className="font-bold">Feedback attribution</h2><p className="mt-1 text-sm text-muted">Guest reports are counted separately from registered accounts.</p><div className="mt-4 grid grid-cols-2 gap-3"><Link to="/control-center/feedback" className="rounded-lg border border-border p-3 hover:border-brand/50"><p className="text-xs text-muted">All reports</p><strong className="text-2xl">{data.feedback.total}</strong></Link><Link to="/control-center/feedback?user_id=guest" className="rounded-lg border border-border p-3 hover:border-brand/50"><p className="text-xs text-muted">Guest reports</p><strong className="text-2xl">{data.feedback.guest}</strong></Link></div></Card>
    </div>
    <Card className="overflow-hidden p-0"><div className="border-b border-border px-4 py-3"><h2 className="font-bold">Recent registrations</h2></div>{data.recent_users.length === 0 ? <p className="p-4 text-sm text-muted">No registered users yet.</p> : <div className="overflow-x-auto"><table className={tableClass}><thead><tr><th>User</th><th>Role</th><th>Status</th><th>Verified</th><th>Created</th></tr></thead><tbody>{data.recent_users.map((user) => <tr key={user.user_id}><td><Link className="block hover:text-brand" to={`/control-center/users?search=${encodeURIComponent(user.email || user.username)}`}><strong>{user.display_name || user.username}</strong><div className="text-xs text-muted">{user.email || user.username}</div></Link></td><td>{user.role}</td><td><Badge tone={user.status === "active" ? "good" : "bad"}>{user.status}</Badge></td><td>{user.email_verified_at ? "Yes" : "No"}</td><td>{formatDate(user.created_at)}</td></tr>)}</tbody></table></div>}</Card>
    <div className="grid gap-5 xl:grid-cols-2">
      <Card className="overflow-hidden p-0"><div className="border-b border-border px-4 py-3"><h2 className="font-bold">Recent feedback</h2></div>{data.recent_feedback.length === 0 ? <p className="p-4 text-sm text-muted">No feedback submitted yet.</p> : <div className="divide-y divide-border">{data.recent_feedback.map((item) => <Link key={item.feedback_id} to={`/control-center/feedback?feedback_id=${item.feedback_id}`} className="block p-4 hover:bg-surface-2"><div className="flex justify-between gap-3"><strong>{item.title}</strong><Badge tone={item.priority === "critical" ? "bad" : "neutral"}>{item.priority}</Badge></div><p className="mt-1 line-clamp-2 text-xs text-muted">{item.username} - {displayLabel(item.category)} - {formatDate(item.created_at)}</p></Link>)}</div>}</Card>
      <Card className="overflow-hidden p-0"><div className="border-b border-border px-4 py-3"><h2 className="font-bold">Recent configuration publications</h2></div>{data.recent_config_publications.length === 0 ? <p className="p-4 text-sm text-muted">No configuration has been published yet.</p> : <div className="divide-y divide-border">{data.recent_config_publications.map((item) => <Link key={item.version} to="/control-center/config" className="block p-4 hover:bg-surface-2"><div className="flex justify-between gap-3"><strong>Version {item.version}</strong><span className="text-xs text-muted">{formatDate(item.created_at)}</span></div><p className="mt-1 text-sm text-muted">{item.reason || "No publication reason"}</p><p className="mt-1 text-xs text-muted">Published by {item.actor_id || "unknown"}</p></Link>)}</div>}</Card>
    </div>
  </div>;
}

export default function OverviewPage() {
  const query = useQuery({ queryKey: ["admin", "overview"], queryFn: api.adminOverview });
  return <><PageHeader title="Operations overview" description="Current account, verification, feedback, and configuration health." /><QueryState loading={query.isLoading} error={query.error}>{query.data && <Dashboard data={query.data} />}</QueryState></>;
}