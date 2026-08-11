import { Info } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useGlossary } from "@/app/hooks/useGlossary";

/**
 * Plain-language glossary: wraps a metric label and shows the beginner
 * definition ("P/E = how much you pay for every ₹1 of profit") on tap/hover.
 * Reads terms from the backend /api/glossary so the copy stays in one place.
 */

interface GlossaryTooltipProps {
  /** Key into the glossary (e.g. "pe", "roe", "score"). */
  term: string;
  children: React.ReactNode;
}

export function GlossaryTooltip({ term, children }: GlossaryTooltipProps) {
  const terms = useGlossary();
  const entry = terms[term];
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: PointerEvent) {
      if (!ref.current?.contains(event.target as Node)) setOpen(false);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  if (!entry) return <span>{children}</span>;

  return (
    <span ref={ref} className="relative inline-flex items-center gap-0.5 align-baseline">
      <button
        type="button"
        className="group inline-flex items-center gap-0.5 focus-visible:outline-none"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <span className="group-hover:text-ink">{children}</span>
        <Info
          aria-hidden="true"
          className="size-3.5 shrink-0 text-muted transition-colors group-hover:text-focus"
        />
      </button>
      {open && (
        <span
          role="tooltip"
          className="absolute top-full left-0 z-50 mt-1.5 w-max max-w-[16rem] rounded-panel border border-border bg-surface-raised px-3 py-2 text-xs leading-5 text-ink shadow-panel"
        >
          <span className="mb-0.5 block font-bold">{entry.term}</span>
          {entry.plain}
        </span>
      )}
    </span>
  );
}
