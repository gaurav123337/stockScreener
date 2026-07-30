import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

interface ToolbarButtonProps {
  label: string;
  active?: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: ReactNode;
}

export function ToolbarButton({
  label,
  active = false,
  disabled = false,
  onClick,
  children,
}: ToolbarButtonProps) {
  return (
    <button
      type="button"
      className={cn(
        "inline-flex size-9 shrink-0 items-center justify-center rounded-lg border border-transparent text-muted transition-colors hover:border-border hover:bg-surface-raised hover:text-ink disabled:cursor-not-allowed disabled:opacity-35 [&_svg]:size-[17px]",
        active && "border-blue-400/50 bg-blue-500/20 text-blue-200",
      )}
      aria-label={label}
      aria-pressed={active}
      title={label}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
