import type { Editor } from "@tiptap/react";
import {
  Bold,
  Highlighter,
  Italic,
  Link as LinkIcon,
  List,
  ListOrdered,
  Redo2,
  RemoveFormatting,
  Strikethrough,
  Undo2,
} from "lucide-react";
import { EmojiPicker } from "./EmojiPicker";
import { ToolbarButton } from "./ToolbarButton";

function normalizeWebUrl(rawValue: string): string | null {
  const value = rawValue.trim();
  if (!value) return "";

  try {
    const url = new URL(/^https?:\/\//i.test(value) ? value : `https://${value}`);
    return url.protocol === "http:" || url.protocol === "https:" ? url.toString() : null;
  } catch {
    return null;
  }
}

interface RichTextToolbarProps {
  editor: Editor | null;
  emojiOpen: boolean;
  onToggleEmoji: () => void;
  onCloseEmoji: () => void;
  onError: (message: string) => void;
}

export function RichTextToolbar({
  editor,
  emojiOpen,
  onToggleEmoji,
  onCloseEmoji,
  onError,
}: RichTextToolbarProps) {
  if (!editor) {
    return (
      <div
        className="min-h-12 rounded-t-panel border border-b-0 border-border bg-canvas"
        aria-hidden
      />
    );
  }
  const activeEditor = editor;

  function setLink() {
    const previous = activeEditor.getAttributes("link").href as string | undefined;
    const value = window.prompt("Enter a link URL", previous ?? "https://");
    if (value === null) return;

    const url = normalizeWebUrl(value);
    if (url === "") {
      activeEditor.chain().focus().extendMarkRange("link").unsetLink().run();
      return;
    }
    if (!url) {
      onError("Enter a valid HTTP or HTTPS link");
      return;
    }
    activeEditor.chain().focus().extendMarkRange("link").setLink({ href: url }).run();
  }

  return (
    <div
      className="relative flex min-h-12 flex-wrap gap-1 rounded-t-panel border border-b-0 border-border bg-canvas p-1.5"
      role="toolbar"
      aria-label="Text formatting"
    >
      <ToolbarButton
        label="Bold"
        active={editor.isActive("bold")}
        onClick={() => editor.chain().focus().toggleBold().run()}
      >
        <Bold />
      </ToolbarButton>
      <ToolbarButton
        label="Italic"
        active={editor.isActive("italic")}
        onClick={() => editor.chain().focus().toggleItalic().run()}
      >
        <Italic />
      </ToolbarButton>
      <ToolbarButton
        label="Strikethrough"
        active={editor.isActive("strike")}
        onClick={() => editor.chain().focus().toggleStrike().run()}
      >
        <Strikethrough />
      </ToolbarButton>
      <ToolbarButton
        label="Highlight concern"
        active={editor.isActive("highlight")}
        onClick={() => editor.chain().focus().toggleHighlight().run()}
      >
        <Highlighter />
      </ToolbarButton>
      <span className="mx-0.5 my-1.5 hidden h-6 w-px bg-border sm:block" aria-hidden />
      <ToolbarButton
        label="Bullet list"
        active={editor.isActive("bulletList")}
        onClick={() => editor.chain().focus().toggleBulletList().run()}
      >
        <List />
      </ToolbarButton>
      <ToolbarButton
        label="Numbered list"
        active={editor.isActive("orderedList")}
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
      >
        <ListOrdered />
      </ToolbarButton>
      <ToolbarButton label="Add or edit link" active={editor.isActive("link")} onClick={setLink}>
        <LinkIcon />
      </ToolbarButton>
      <EmojiPicker
        editor={editor}
        open={emojiOpen}
        onToggle={onToggleEmoji}
        onClose={onCloseEmoji}
      />
      <span className="mx-0.5 my-1.5 hidden h-6 w-px bg-border sm:block" aria-hidden />
      <ToolbarButton
        label="Clear formatting"
        onClick={() => editor.chain().focus().unsetAllMarks().clearNodes().run()}
      >
        <RemoveFormatting />
      </ToolbarButton>
      <ToolbarButton
        label="Undo"
        disabled={!editor.can().chain().focus().undo().run()}
        onClick={() => editor.chain().focus().undo().run()}
      >
        <Undo2 />
      </ToolbarButton>
      <ToolbarButton
        label="Redo"
        disabled={!editor.can().chain().focus().redo().run()}
        onClick={() => editor.chain().focus().redo().run()}
      >
        <Redo2 />
      </ToolbarButton>
    </div>
  );
}
