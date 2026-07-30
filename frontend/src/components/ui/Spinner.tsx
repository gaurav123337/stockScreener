import { cn } from "@/lib/cn";
import { LoaderCircle } from "lucide-react";
import type { ReactNode } from "react";

export function Spinner({ className }: { className?: string }) {
  return <LoaderCircle className={cn("size-4 animate-spin", className)} aria-hidden />;
}

export function LoadingState({ children = "Loading…" }: { children?: ReactNode }) {
  return (
    <div
      className="flex items-center justify-center gap-2 px-6 py-8 text-center text-sm text-muted"
      role="status"
    >
      <Spinner />
      <span>{children}</span>
    </div>
  );
}
