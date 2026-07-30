import { api } from "@/api/endpoints";
import { useToast } from "@/app/useToast";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { controlClass } from "@/components/ui/styles";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Badge, PageHeader, QueryState } from "./shared";
import { formatDate, tableClass } from "./table-utils";

export default function UsersPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [role, setRole] = useState("");
  const { toast } = useToast();
  const client = useQueryClient();
  const params = new URLSearchParams();
  if (search) params.set("search", search);
  if (status) params.set("status", status);
  if (role) params.set("role", role);
  const query = useQuery({
    queryKey: ["admin", "users", search, status, role],
    queryFn: () => api.adminUsers(params.toString()),
  });
  const resetMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      api.sendAdminPasswordReset(id, reason),
    onSuccess: () => toast("Password reset invitation requested"),
    onError: (error) => toast(error instanceof Error ? error.message : "Reset invitation failed"),
  });
  const mutation = useMutation({
    mutationFn: ({ id, next, reason }: { id: string; next: string; reason: string }) =>
      api.setAdminUserStatus(id, next, reason),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["admin"] });
      toast("Account status updated");
    },
  });
  function change(id: string, current: string) {
    const next = current === "active" ? "suspended" : "active";
    const reason = window.prompt(
      `Reason to ${next === "active" ? "reactivate" : "suspend"} this account:`,
    );
    if (reason?.trim()) mutation.mutate({ id, next, reason: reason.trim() });
  }
  function sendReset(id: string) {
    const reason = window.prompt("Reason for sending this password reset invitation:");
    if (reason?.trim()) resetMutation.mutate({ id, reason: reason.trim() });
  }
  return (
    <>
      <PageHeader
        title="User operations"
        description="Search accounts, review verification state, and control access."
        actions={<div className="text-sm text-muted">{query.data?.total ?? 0} accounts</div>}
      />
      <div className="mb-4 grid gap-2 sm:grid-cols-[minmax(0,1fr)_12rem_12rem]">
        <input
          className={controlClass}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search name, username, or email"
        />
        <select className={controlClass} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="suspended">Suspended</option>
        </select>
        <select className={controlClass} value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="">All roles</option>
          <option value="user">User</option>
          <option value="product_owner">Product owner</option>
        </select>
      </div>
      <QueryState loading={query.isLoading} error={query.error}>
        {query.data && (
          <Card className="overflow-hidden p-0">
            <div className="overflow-x-auto">
              <table className={tableClass}>
                <thead>
                  <tr>
                    <th>User</th>
                    <th>Verification</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th>Last login</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {query.data.items.map((user) => (
                    <tr key={user.user_id}>
                      <td>
                        <strong>{user.display_name || user.username}</strong>
                        <div className="text-xs text-muted">{user.email || user.username}</div>
                      </td>
                      <td>
                        <Badge tone={user.email_verified_at ? "good" : "warn"}>
                          {user.email_verified_at ? "Verified" : "Pending"}
                        </Badge>
                      </td>
                      <td>{user.role}</td>
                      <td>
                        <Badge tone={user.status === "active" ? "good" : "bad"}>
                          {user.status}
                        </Badge>
                      </td>
                      <td>{formatDate(user.last_login_at)}</td>
                      <td>
                        <div className="flex gap-2">
                          <Button
                            fullWidth={false}
                            variant="secondary"
                            className="min-h-9 px-3 py-1"
                            disabled={resetMutation.isPending || !user.email || user.status !== "active"}
                            onClick={() => sendReset(user.user_id)}
                          >
                            Reset link
                          </Button>
                          <Button
                            fullWidth={false}
                            variant={user.status === "active" ? "danger" : "secondary"}
                            className="min-h-9 px-3 py-1"
                            disabled={mutation.isPending || user.role === "product_owner"}
                            onClick={() => change(user.user_id, user.status)}
                          >
                            {user.status === "active" ? "Suspend" : "Reactivate"}
                          </Button>
                        </div>
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
