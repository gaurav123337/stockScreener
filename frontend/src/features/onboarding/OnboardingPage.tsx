import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Check, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/api/endpoints";
import { useToast } from "@/app/useToast";
import { AssetSplitBar } from "@/components/AssetSplitBar";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { LoadingState } from "@/components/ui/Spinner";
import { cn } from "@/lib/cn";
import { useAuth } from "@/features/auth/auth-context";
import type { RiskProfile } from "@/types/api";

export default function OnboardingPage() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { user } = useAuth();
  const questionsQuery = useQuery({ queryKey: ["onboarding"], queryFn: api.onboardingQuestions });
  const profileQuery = useQuery({ queryKey: ["risk-profile"], queryFn: api.getRiskProfile });

  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [done, setDone] = useState<RiskProfile | null>(null);

  const saveMutation = useMutation({
    mutationFn: api.saveRiskProfile,
    onSuccess: (profile) => {
      setDone(profile);
      toast("Your risk profile is ready");
    },
    onError: (e) => toast(e instanceof Error ? e.message : "Could not save your profile"),
  });

  const questions = useMemo(() => questionsQuery.data?.questions ?? [], [questionsQuery.data]);
  const saved = profileQuery.data;
  const existing =
    saved && saved.level ? (saved as RiskProfile) : done;

  const allAnswered = useMemo(
    () => questions.every((q) => Boolean(answers[q.id])),
    [questions, answers],
  );

  if (questionsQuery.isLoading || profileQuery.isLoading) {
    return <LoadingState>Loading the questions…</LoadingState>;
  }

  if (existing) {
    return (
      <>
        <div className="mb-5">
          <h1 className="text-2xl font-bold text-ink">Your risk profile</h1>
          <p className="mt-1 text-sm text-muted">
            Based on your answers, you are a <strong>{existing.label}</strong> investor.
          </p>
        </div>
        <Card>
          <CardTitle>{existing.label} — suggested mix</CardTitle>
          <p className="mt-2 text-sm leading-6 text-muted">{existing.summary}</p>
          <div className="mt-4">
            <AssetSplitBar split={existing.asset_split} />
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button onClick={() => navigate("/plan")}>
              <Sparkles className="size-4" aria-hidden /> Build my starter plan
            </Button>
            <Button
              variant="secondary"
              fullWidth={false}
              onClick={() => {
                setDone(null);
                setStep(0);
                setAnswers({});
              }}
            >
              Retake the quiz
            </Button>
          </div>
        </Card>
      </>
    );
  }

  const question = questions[step];

  return (
    <>
      <div className="mb-5">
        <h1 className="text-2xl font-bold text-ink">Let&apos;s build your starter plan</h1>
        <p className="mt-1 text-sm text-muted">
          {user?.username ?? "A few"} quick questions — no jargon, no wrong answers. This shapes
          the plan we suggest.
        </p>
      </div>

      <Card>
        <div className="mb-4 flex items-center justify-between text-xs text-muted">
          <span>
            Step {Math.min(step + 1, questions.length)} of {questions.length}
          </span>
          <div className="h-1.5 w-24 overflow-hidden rounded-full bg-surface-raised">
            <div
              className="h-full rounded-full bg-brand transition-all"
              style={{ width: `${((step + 1) / Math.max(questions.length, 1)) * 100}%` }}
            />
          </div>
        </div>

        {question ? (
          <div key={question.id}>
            <h2 className="text-lg font-bold text-ink">{question.question}</h2>
            <div className="mt-4 grid gap-2">
              {question.options.map((option) => {
                const selected = answers[question.id] === option.value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    className={cn(
                      "flex min-h-12 items-center justify-between gap-3 rounded-lg border px-3.5 py-2.5 text-left text-sm font-semibold transition-colors",
                      selected
                        ? "border-brand bg-brand/10 text-ink"
                        : "border-border bg-surface-raised text-muted hover:border-muted hover:text-ink",
                    )}
                    aria-pressed={selected}
                    onClick={() => {
                      setAnswers((current) => ({ ...current, [question.id]: option.value }));
                      if (step < questions.length - 1) setStep(step + 1);
                    }}
                  >
                    {option.label}
                    {selected && <Check className="size-4 shrink-0 text-brand" aria-hidden />}
                  </button>
                );
              })}
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted">No questions are available right now.</p>
        )}

        <div className="mt-5 flex items-center justify-between gap-2">
          <Button
            variant="secondary"
            fullWidth={false}
            disabled={step === 0}
            onClick={() => setStep((current) => Math.max(0, current - 1))}
          >
            <ArrowLeft className="size-4" aria-hidden /> Back
          </Button>
          {step === questions.length - 1 ? (
            <Button
              disabled={!allAnswered || saveMutation.isPending}
              onClick={() => {
                if (allAnswered) saveMutation.mutate(answers);
              }}
            >
              {saveMutation.isPending ? "Saving…" : "Show my profile"}
              {!saveMutation.isPending && <ArrowRight className="size-4" aria-hidden />}
            </Button>
          ) : (
            <Button
              variant="secondary"
              fullWidth={false}
              disabled={!answers[question?.id ?? ""]}
              onClick={() => setStep((current) => Math.min(questions.length - 1, current + 1))}
            >
              Next <ArrowRight className="size-4" aria-hidden />
            </Button>
          )}
        </div>
      </Card>
    </>
  );
}
