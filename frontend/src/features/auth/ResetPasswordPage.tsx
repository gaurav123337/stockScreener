import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { Button } from "@/components/ui/Button";
import { controlClass, labelClass } from "@/components/ui/styles";
import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AuthCard } from "./ForgotPasswordPage";

export default function ResetPasswordPage() {
  const [params] = useSearchParams(); const token = params.get("token") || "";
  const [password, setPassword] = useState(""); const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState(""); const [error, setError] = useState("");
  async function submit(event: FormEvent) { event.preventDefault(); setError(""); try { setMessage((await api.resetPassword(token, password, confirmation)).message); } catch (err) { setError(err instanceof ApiError ? err.message : "Unable to reset password"); } }
  return <AuthCard title="Choose a new password"><form className="grid gap-4" onSubmit={submit}><label className={labelClass}>New password<input className={controlClass} type="password" minLength={8} required value={password} onChange={(e) => setPassword(e.target.value)} /></label><label className={labelClass}>Confirm password<input className={controlClass} type="password" minLength={8} required value={confirmation} onChange={(e) => setConfirmation(e.target.value)} /></label>{error && <p className="text-sm text-danger" role="alert">{error}</p>}{message && <p className="text-sm text-brand" role="status">{message}</p>}<Button disabled={!token}>Reset password</Button>{message && <Link className="text-center text-sm font-semibold text-focus" to="/auth/login">Sign in</Link>}</form></AuthCard>;
}