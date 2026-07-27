import { lazy } from "react";
import { createHashRouter, Navigate } from "react-router-dom";
import { AppLayout } from "./layout/AppLayout";

/**
 * HashRouter mirrors the legacy `#/tab` routing and keeps FastAPI static
 * serving trivial — no history-API fallback configuration needed.
 * Each tab is lazy-loaded for a small initial bundle.
 */
const RecommendPage = lazy(() => import("@/features/recommend/RecommendPage"));
const ScanPage = lazy(() => import("@/features/scan/ScanPage"));
const TrainPage = lazy(() => import("@/features/train/TrainPage"));
const BrokersPage = lazy(() => import("@/features/brokers/BrokersPage"));
const SettingsPage = lazy(() => import("@/features/settings/SettingsPage"));
const GuidePage = lazy(() => import("@/features/guide/GuidePage"));

export const router = createHashRouter([
  {
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/recommend" replace /> },
      { path: "recommend", element: <RecommendPage /> },
      { path: "scan", element: <ScanPage /> },
      { path: "train", element: <TrainPage /> },
      { path: "brokers", element: <BrokersPage /> },
      { path: "settings", element: <SettingsPage /> },
      { path: "guide", element: <GuidePage /> },
      { path: "*", element: <Navigate to="/recommend" replace /> },
    ],
  },
]);
