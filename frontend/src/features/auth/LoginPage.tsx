import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "./auth-context";
import { ApiError } from "@/api/client";
import { useToast } from "@/app/useToast";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { controlClass, labelClass } from "@/components/ui/styles";

export default function LoginPage() {
  const { login } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (!username.trim() || !password) {
      setError("Please enter both username and password");
      return;
    }
    setLoading(true);
    try {
      await login(username.trim(), password);
      toast("Logged in successfully!");
      navigate("/recommend", { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Login failed. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-[60vh] max-w-md items-center">
      <Card className="w-full">
        <h1 className="text-2xl font-bold">Sign in</h1>
        <p className="mt-1 text-sm text-muted">Welcome back to stockScreener</p>

        {error && (
          <div
            className="mt-4 rounded-lg border border-rose-500/40 bg-rose-500/10 p-3 text-sm text-rose-200"
            role="alert"
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-5 grid gap-4">
          <label className={labelClass} htmlFor="login-username">
            Username
            <input
              id="login-username"
              className={controlClass}
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter username"
              autoComplete="username"
              disabled={loading}
            />
          </label>

          <label className={labelClass} htmlFor="login-password">
            Password
            <input
              id="login-password"
              className={controlClass}
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter password"
              autoComplete="current-password"
              disabled={loading}
            />
          </label>

          <Button type="submit" disabled={loading}>
            {loading ? "Signing in…" : "Sign In"}
          </Button>
        </form>

        <p className="mt-5 text-center text-sm text-muted [&_a]:font-semibold [&_a]:text-blue-300 [&_a]:hover:underline">
          Don't have an account? <Link to="/auth/register">Create one</Link>
        </p>
        <p className="mt-2 text-center text-sm text-muted [&_a]:font-semibold [&_a]:text-blue-300 [&_a]:hover:underline">
          <Link to="/recommend">Continue as guest</Link>
        </p>
      </Card>
    </div>
  );
}
