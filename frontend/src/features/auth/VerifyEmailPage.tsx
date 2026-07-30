import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AuthCard } from "./ForgotPasswordPage";

export default function VerifyEmailPage() {
  const [params] = useSearchParams(); const token = params.get("token") || "";
  const [message, setMessage] = useState("Verifying your email…");
  useEffect(() => { if (!token) { setMessage("This verification link is incomplete."); return; } api.verifyEmail(token).then(() => setMessage("Email verified successfully.")).catch((error) => setMessage(error instanceof ApiError ? error.message : "Unable to verify email.")); }, [token]);
  return <AuthCard title="Email verification"><p className="text-sm text-muted" role="status">{message}</p><Link className="mt-5 block text-sm font-semibold text-focus" to="/auth/login">Continue to sign in</Link></AuthCard>;
}