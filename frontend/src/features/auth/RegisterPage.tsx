import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "./auth-context";
import { ApiError } from "@/api/client";
import { useToast } from "@/app/useToast";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { controlClass, labelClass } from "@/components/ui/styles";

export default function RegisterPage() {
  const { register } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");

    if (!email.trim() || !password) {
      setError("Please fill in all required fields");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match");
      return;
    }

    setLoading(true);
    try {
      await register(email.trim(), password, confirm, displayName.trim() || undefined);
      toast("Account created. Check your email to verify it.");
      navigate("/onboarding", { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Registration failed. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-[60vh] max-w-md items-center">
      <Card className="w-full">
        <h1 className="text-2xl font-bold">Create account</h1>
        <p className="mt-1 text-sm text-muted">Join stockScreener to save your preferences</p>

        {error && (
          <div
            className="mt-4 rounded-lg border border-rose-500/40 bg-rose-500/10 p-3 text-sm text-danger"
            role="alert"
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-5 grid gap-4">
          <label className={labelClass} htmlFor="register-email">
            Email *
            <input
              id="register-email"
              className={controlClass}
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
              disabled={loading}
            />
          </label>

          <label className={labelClass} htmlFor="register-display-name">
            Display Name
            <input
              id="register-display-name"
              className={controlClass}
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Your name (optional)"
              disabled={loading}
            />
          </label>

          <label className={labelClass} htmlFor="register-password">
            Password *
            <input
              id="register-password"
              className={controlClass}
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Choose a password"
              autoComplete="new-password"
              disabled={loading}
            />
          </label>

          <label className={labelClass} htmlFor="register-confirm-password">
            Confirm Password *
            <input
              id="register-confirm-password"
              className={controlClass}
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="Confirm your password"
              autoComplete="new-password"
              disabled={loading}
            />
          </label>

          <Button type="submit" disabled={loading}>
            {loading ? "Creating account…" : "Create Account"}
          </Button>
        </form>

        <p className="mt-5 text-center text-sm text-muted [&_a]:font-semibold [&_a]:text-focus [&_a]:hover:underline">
          Already have an account? <Link to="/auth/login">Sign in</Link>
        </p>
        <p className="mt-2 text-center text-sm text-muted [&_a]:font-semibold [&_a]:text-focus [&_a]:hover:underline">
          <Link to="/recommend">Continue as guest</Link>
        </p>
      </Card>
    </div>
  );
}
