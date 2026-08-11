import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "./auth-context";
import { api } from "@/api/endpoints";
import { ApiError } from "@/api/client";
import { useToast } from "@/app/useToast";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { controlClass, labelClass } from "@/components/ui/styles";

export default function LoginPage() {
  const { login } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (!email.trim() || !password) {
      setError("Please enter both email and password");
      return;
    }
    setLoading(true);
    try {
      const profile = await login(email.trim(), password);
      toast("Logged in successfully!");
      if (profile.role === "product_owner") {
        navigate("/control-center", { replace: true });
        return;
      }
      // Beginner flow: send a first-time user to the risk questionnaire so the
      // 3–5 holding starter plan is built on their real answers.
      try {
        const risk = await api.getRiskProfile();
        navigate(risk.level ? "/recommend" : "/onboarding", { replace: true });
      } catch {
        navigate("/recommend", { replace: true });
      }
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
            className="mt-4 rounded-lg border border-rose-500/40 bg-rose-500/10 p-3 text-sm text-danger"
            role="alert"
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-5 grid gap-4">
          <label className={labelClass} htmlFor="login-email">
            Email
            <input
              id="login-email"
              className={controlClass}
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
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

          <div className="text-right"><Link className="text-sm font-semibold text-focus hover:underline" to="/auth/forgot-password">Forgot password?</Link></div>
          <Button type="submit" disabled={loading}>
            {loading ? "Signing in…" : "Sign In"}
          </Button>
        </form>

        <p className="mt-5 text-center text-sm text-muted [&_a]:font-semibold [&_a]:text-focus [&_a]:hover:underline">
          Don't have an account? <Link to="/auth/register">Create one</Link>
        </p>
        <p className="mt-2 text-center text-sm text-muted [&_a]:font-semibold [&_a]:text-focus [&_a]:hover:underline">
          <Link to="/recommend">Continue as guest</Link>
        </p>
      </Card>
    </div>
  );
}
