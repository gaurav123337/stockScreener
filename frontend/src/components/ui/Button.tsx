import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const variants: Record<ButtonVariant, string> = {
  primary: "bg-brand text-emerald-950 hover:bg-emerald-400",
  secondary:
    "border border-border bg-surface-raised text-ink hover:border-slate-500 hover:bg-slate-700/60",
  ghost:
    "border border-dashed border-border bg-transparent text-blue-300 hover:border-focus hover:bg-blue-500/10",
  danger: "border border-rose-500/40 bg-rose-500/10 text-rose-300 hover:bg-rose-500/20",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  fullWidth?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant = "primary", fullWidth = true, type = "button", ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cn(
        "inline-flex min-h-11 items-center justify-center gap-2 rounded-panel px-4 py-2.5 text-sm font-bold transition active:scale-[0.98] disabled:pointer-events-none disabled:opacity-60",
        variants[variant],
        fullWidth && "w-full",
        className,
      )}
      {...props}
    />
  );
});
