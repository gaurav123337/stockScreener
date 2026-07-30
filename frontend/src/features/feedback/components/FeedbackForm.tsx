import { useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { MessageSquareHeart } from "lucide-react";
import { api } from "@/api/endpoints";
import { useToast } from "@/app/useToast";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { controlClass, labelClass } from "@/components/ui/styles";
import type { FeedbackCategory } from "@/types/api";
import {
  CATEGORY_OPTIONS,
  DETAILS_MAX,
  DETAILS_MIN,
  TITLE_MAX,
  TITLE_MIN,
} from "../feedbackConfig";
import { useFeedbackEditor } from "../hooks/useFeedbackEditor";
import { RichTextField } from "./RichTextField";

export function FeedbackForm() {
  const { toast } = useToast();
  const [category, setCategory] = useState<FeedbackCategory>("concern");
  const [title, setTitle] = useState("");
  const [emojiOpen, setEmojiOpen] = useState(false);
  const [detailsCount, setDetailsCount] = useState(0);
  const [formError, setFormError] = useState("");
  const editor = useFeedbackEditor(setDetailsCount, () => setFormError(""));

  const mutation = useMutation({
    mutationFn: api.submitFeedback,
    onSuccess: (receipt) => {
      toast(receipt.message);
      setCategory("concern");
      setTitle("");
      setEmojiOpen(false);
      setDetailsCount(0);
      setFormError("");
      editor?.commands.clearContent();
    },
    onError: (error) =>
      showError(error instanceof Error ? error.message : "Feedback submission failed"),
  });

  function showError(message: string) {
    setFormError(message);
    toast(message);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editor || mutation.isPending) return;

    const cleanTitle = title.trim();
    const plainText = editor.getText().trim();
    if (cleanTitle.length < TITLE_MIN || cleanTitle.length > TITLE_MAX) {
      showError(`Add a title between ${TITLE_MIN} and ${TITLE_MAX} characters`);
      return;
    }
    if (Array.from(plainText).length < DETAILS_MIN || detailsCount > DETAILS_MAX) {
      showError(
        `Describe your feedback using ${DETAILS_MIN}–${DETAILS_MAX.toLocaleString()} characters`,
      );
      editor.commands.focus();
      return;
    }

    setFormError("");
    mutation.mutate({
      category,
      title: cleanTitle,
      document: editor.getJSON(),
      plain_text: plainText,
    });
  }

  return (
    <form onSubmit={submit}>
      <Card className="p-4 sm:p-5">
        <FeedbackNotice />
        <div className="grid gap-5">
          <label className={labelClass} htmlFor="feedback-category">
            Feedback type
            <select
              id="feedback-category"
              className={controlClass}
              value={category}
              onChange={(event) => setCategory(event.target.value as FeedbackCategory)}
            >
              {CATEGORY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className={labelClass} htmlFor="feedback-title">
            Short title
            <input
              id="feedback-title"
              className={controlClass}
              value={title}
              onChange={(event) => {
                setTitle(event.target.value);
                setFormError("");
              }}
              minLength={TITLE_MIN}
              maxLength={TITLE_MAX}
              placeholder="Example: The score explanation is unclear"
              required
            />
            <small className="text-right text-xs font-normal text-muted">
              {title.length}/{TITLE_MAX}
            </small>
          </label>
          <RichTextField
            editor={editor}
            count={detailsCount}
            emojiOpen={emojiOpen}
            onToggleEmoji={() => setEmojiOpen((open) => !open)}
            onCloseEmoji={() => setEmojiOpen(false)}
            onError={showError}
          />
        </div>
        {formError && (
          <div
            className="mt-4 rounded-lg border border-rose-500/40 bg-rose-500/10 p-3 text-sm text-rose-200"
            role="alert"
          >
            {formError}
          </div>
        )}
        <Button className="mt-5" type="submit" disabled={!editor || mutation.isPending}>
          {mutation.isPending ? "Sending feedback…" : "Send feedback"}
        </Button>
      </Card>
    </form>
  );
}

function FeedbackNotice() {
  return (
    <div className="mb-5 flex items-start gap-3 rounded-xl border border-blue-500/30 bg-blue-500/10 p-3.5 text-blue-200">
      <MessageSquareHeart className="mt-0.5 size-5 shrink-0" aria-hidden />
      <div>
        <strong className="block text-sm">Your feedback shapes the next test build</strong>
        <span className="mt-0.5 block text-[13px] text-muted">
          Emoji and rich formatting will be preserved with your submission.
        </span>
      </div>
    </div>
  );
}
