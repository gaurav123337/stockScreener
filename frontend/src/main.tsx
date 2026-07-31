import { initializeFontSize } from "@/app/hooks/useFontSize";
import { initializeTheme } from "@/app/hooks/useTheme";
import { queryClient } from "@/app/queryClient";
import { router } from "@/app/router";
import { ToastProvider } from "@/app/toast";
import { AuthProvider } from "@/features/auth/AuthProvider";
import "@/styles/global.css";
import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router-dom";

initializeTheme();
initializeFontSize();

const container = document.getElementById("root");
if (!container) throw new Error("Root element #root not found");

createRoot(container).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AuthProvider>
          <Suspense fallback={null}>
            <RouterProvider router={router} />
          </Suspense>
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>
  </StrictMode>,
);
