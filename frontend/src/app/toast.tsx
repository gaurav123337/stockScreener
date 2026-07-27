import { useCallback, useMemo, useRef, useState, type ReactNode } from "react";
import { ToastContext, type ToastContextValue } from "./toast-context";

interface ToastState {
  id: number;
  message: string;
}

const DEFAULT_DURATION = 2600;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [current, setCurrent] = useState<ToastState | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const toast = useCallback((message: string, durationMs = DEFAULT_DURATION) => {
    if (timer.current) clearTimeout(timer.current);
    setCurrent({ id: Date.now(), message });
    timer.current = setTimeout(() => setCurrent(null), durationMs);
  }, []);

  const value = useMemo<ToastContextValue>(() => ({ toast }), [toast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      {current && (
        <div key={current.id} className="toast" role="status" aria-live="polite">
          {current.message}
        </div>
      )}
    </ToastContext.Provider>
  );
}
