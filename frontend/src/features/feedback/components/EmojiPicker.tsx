import type { Editor } from "@tiptap/react";
import { ToolbarButton } from "./ToolbarButton";

const EMOJI = ["👍", "👎", "🙂", "😕", "😟", "🐛", "💡", "🚨", "✅", "🙏", "🎯", "📱"];

export function EmojiPicker(props: {
  editor: Editor;
  open: boolean;
  onToggle: () => void;
  onClose: () => void;
}) {
  return (
    <div className="relative">
      <ToolbarButton label="Insert emoji" active={props.open} onClick={props.onToggle}>
        <span className="text-[17px] leading-none">😊</span>
      </ToolbarButton>
      {props.open && (
        <div
          className="absolute top-10 left-0 z-20 grid w-44 max-w-[calc(100vw-2rem)] grid-cols-4 gap-1 rounded-lg border border-border bg-surface p-2 shadow-panel"
          role="dialog"
          aria-label="Choose an emoji"
        >
          {EMOJI.map((emoji) => (
            <button
              key={emoji}
              type="button"
              className="flex size-10 items-center justify-center rounded-lg border border-transparent bg-surface-raised text-xl hover:border-focus"
              aria-label={`Insert ${emoji}`}
              onClick={() => {
                props.editor.chain().focus().insertContent(emoji).run();
                props.onClose();
              }}
              onMouseDown={(event) => event.preventDefault()}
            >
              {emoji}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
