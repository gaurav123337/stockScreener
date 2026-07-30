import { EditorContent, type Editor } from "@tiptap/react";
import { helpTextClass } from "@/components/ui/styles";
import { cn } from "@/lib/cn";
import { DETAILS_MAX } from "../feedbackConfig";
import { RichTextToolbar } from "./RichTextToolbar";

interface RichTextFieldProps {
  editor: Editor | null;
  count: number;
  emojiOpen: boolean;
  onToggleEmoji: () => void;
  onCloseEmoji: () => void;
  onError: (message: string) => void;
}

export function RichTextField(props: RichTextFieldProps) {
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between gap-3">
        <span className="text-sm font-semibold text-slate-200">Details</span>
        <small
          id="feedback-details-count"
          className={cn(
            "text-xs text-muted",
            props.count >= DETAILS_MAX * 0.9 && "text-yellow-300",
          )}
        >
          {props.count.toLocaleString()}/{DETAILS_MAX.toLocaleString()}
        </small>
      </div>
      <RichTextToolbar
        editor={props.editor}
        emojiOpen={props.emojiOpen}
        onToggleEmoji={props.onToggleEmoji}
        onCloseEmoji={props.onCloseEmoji}
        onError={props.onError}
      />
      <div className="min-h-56 rounded-b-panel border border-border bg-surface-raised transition focus-within:border-focus focus-within:ring-1 focus-within:ring-focus">
        <EditorContent editor={props.editor} />
      </div>
      <p id="feedback-details-help" className={cn(helpTextClass, "mt-2")}>
        Include what you expected, what happened, and any steps that help us reproduce it.
      </p>
    </div>
  );
}
