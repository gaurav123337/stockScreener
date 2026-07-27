import { createContext } from "react";

export interface ToastContextValue {
  toast: (message: string, durationMs?: number) => void;
}

export const ToastContext = createContext<ToastContextValue | null>(null);
