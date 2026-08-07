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
const FeedbackPage = lazy(() => import("@/features/feedback/FeedbackPage"));
const LoginPage = lazy(() => import("@/features/auth/LoginPage"));
const RegisterPage = lazy(() => import("@/features/auth/RegisterPage"));
const ForgotPasswordPage = lazy(() => import("@/features/auth/ForgotPasswordPage"));
const ResetPasswordPage = lazy(() => import("@/features/auth/ResetPasswordPage"));
const VerifyEmailPage = lazy(() => import("@/features/auth/VerifyEmailPage"));
const IndianMarketPage = lazy(() => import("@/features/indian-market/IndianMarketPage"));
const MutualFundsPage = lazy(() => import("@/features/mutual-funds/MutualFundsPage"));
const TrackRecordPage = lazy(() => import("@/features/track-record/TrackRecordPage"));
const OnboardingPage = lazy(() => import("@/features/onboarding/OnboardingPage"));
const PlanPage = lazy(() => import("@/features/plan/PlanPage"));
const PortfolioPage = lazy(() => import("@/features/portfolio/PortfolioPage"));
const ControlCenterLayout = lazy(() => import("@/features/control-center/ControlCenterLayout"));
const OverviewPage = lazy(() => import("@/features/control-center/OverviewPage"));
const UsersPage = lazy(() => import("@/features/control-center/UsersPage"));
const FeedbackOpsPage = lazy(() => import("@/features/control-center/FeedbackOpsPage"));
const ConfigPage = lazy(() => import("@/features/control-center/ConfigPage"));
const AuditPage = lazy(() => import("@/features/control-center/AuditPage"));
const IndexRedirect = lazy(() => import("./IndexRedirect"));

export const router = createHashRouter([
  {
    path: "control-center",
    element: <ControlCenterLayout />,
    children: [
      { index: true, element: <OverviewPage /> },
      { path: "users", element: <UsersPage /> },
      { path: "feedback", element: <FeedbackOpsPage /> },
      { path: "config", element: <ConfigPage /> },
      { path: "audit", element: <AuditPage /> },
    ],
  },
  {
    element: <AppLayout />,
    children: [
      { index: true, element: <IndexRedirect /> },
      { path: "recommend", element: <RecommendPage /> },
      { path: "onboarding", element: <OnboardingPage /> },
      { path: "plan", element: <PlanPage /> },
      { path: "portfolio", element: <PortfolioPage /> },
      { path: "scan", element: <ScanPage /> },
      { path: "train", element: <TrainPage /> },
      { path: "brokers", element: <BrokersPage /> },
      { path: "indian-market", element: <IndianMarketPage /> },
      { path: "mutual-funds", element: <MutualFundsPage /> },
      { path: "track-record", element: <TrackRecordPage /> },
      { path: "settings", element: <SettingsPage /> },
      { path: "guide", element: <GuidePage /> },
      { path: "feedback", element: <FeedbackPage /> },
      { path: "auth/login", element: <LoginPage /> },
      { path: "auth/register", element: <RegisterPage /> },
      { path: "auth/forgot-password", element: <ForgotPasswordPage /> },
      { path: "auth/reset-password", element: <ResetPasswordPage /> },
      { path: "auth/verify-email", element: <VerifyEmailPage /> },
      { path: "*", element: <Navigate to="/recommend" replace /> },
    ],
  },
]);
