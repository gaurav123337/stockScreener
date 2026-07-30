import { api } from "@/api/endpoints";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { controlClass, labelClass } from "@/components/ui/styles";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setLoading(true);
    try { setMessage((await api.forgotPassword(email)).message); }
    finally { setLoading(false); }
  }
  return <AuthCard title="Reset your password"><form className="grid gap-4" onSubmit={submit}><label className={labelClass}>Email<input className={controlClass} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></label>{message && <p className="text-sm text-brand" role="status">{message}</p>}<Button disabled={loading}>{loading ? "Sending…" : "Send reset link"}</Button><Link className="text-center text-sm font-semibold text-focus" to="/auth/login">Back to sign in</Link></form></AuthCard>;
}

export function AuthCard({ title, children }: { title: string; children: React.ReactNode }) {
  return <div className="mx-auto flex min-h-[60vh] max-w-md items-center"><Card className="w-full"><h1 className="mb-5 text-2xl font-bold">{title}</h1>{children}</Card></div>;
}