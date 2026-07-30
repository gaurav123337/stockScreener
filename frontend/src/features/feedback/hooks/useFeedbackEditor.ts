import CharacterCount from "@tiptap/extension-character-count";
import Highlight from "@tiptap/extension-highlight";
import Link from "@tiptap/extension-link";
import { useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { DETAILS_MAX } from "../feedbackConfig";

export function useFeedbackEditor(onCountChange: (count: number) => void, onEdit: () => void) {
  return useEditor({
    extensions: [
      StarterKit.configure({ link: false }),
      Highlight.configure({ multicolor: false }),
      Link.configure({ openOnClick: false, autolink: true }),
      CharacterCount.configure({
        limit: DETAILS_MAX,
        textCounter: (text) => Array.from(text).length,
      }),
    ],
    content: "",
    editorProps: {
      attributes: {
        class: "feedback-editor",
        "aria-label": "Feedback details",
        "aria-describedby": "feedback-details-help feedback-details-count",
      },
    },
    onCreate: ({ editor }) => onCountChange(editor.storage.characterCount.characters()),
    onUpdate: ({ editor }) => {
      onCountChange(editor.storage.characterCount.characters());
      onEdit();
    },
  });
}
