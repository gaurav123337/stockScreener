# Feedback Form Implementation Plan

**Timestamp:** **2026-07-30T07:06:37Z (UTC) | 30-07-2026 12:36:37 (IST)**

## Overview

Add a tester feedback workflow to the React application. Test users can categorize a submission, add a short title, and describe concerns in a rich-text editor with formatting, text highlighting, lists, links, undo/redo, and emoji insertion.

## Current State Analysis

- `frontend/src/app/router.tsx` and `frontend/src/app/layout/AppLayout.tsx` define a lazy-loaded, hash-routed tab interface.
- `frontend/src/api/endpoints.ts` provides typed frontend wrappers for FastAPI endpoints.
- `api.py` exposes structured JSON APIs and resolves the current authenticated or guest user.
- SQLite already persists user data, but there is no feedback model, service, endpoint, or frontend form.
- The frontend does not currently include a rich-text editor or icon library.

## Implementation Phases

1. **Persistence and domain service**
   - Add a SQLite-backed feedback store with user attribution and timestamps.
   - Store structured editor JSON and a plain-text projection; do not persist executable HTML.
   - Validate categories, title length, text length, document shape, and serialized size.
2. **API integration**
   - Add a typed `POST /api/feedback` endpoint scoped through the existing user dependency.
   - Return a stable receipt containing the feedback ID and creation timestamp.
3. **Frontend experience**
   - Add a lazy-loaded Feedback route and primary navigation item.
   - Build a TipTap rich-text editor toolbar with accessible icon controls, highlighting, link editing, and an emoji picker.
   - Add submission validation, pending/error/success states, and reset the form after success.
4. **Verification**
   - Add offline unit tests for persistence, tenant attribution, rich document and emoji preservation, and validation.
   - Run Python tests, frontend lint/type checks, and production build.

## Technical Considerations

- TipTap is used as the maintained rich-text editing toolkit, with StarterKit and Highlight extensions.
- Structured JSON is safer and more portable than trusting client-generated HTML. The plain-text projection supports searching and triage.
- Emoji are regular Unicode text nodes, so they survive JSON serialization without a custom backend format.
- The endpoint accepts guest submissions for backward compatibility while attributing signed-in submissions to their user ID.
- The implementation follows the existing service locator and typed endpoint conventions.

## Success Criteria

- A Feedback tab is available on mobile and desktop layouts.
- Users can format text, highlight concerns, insert emoji, and submit valid feedback.
- Empty, oversized, or malformed feedback is rejected with the existing structured error format.
- Stored records preserve structured formatting and Unicode emoji and identify the submitting tenant.
- Existing tests pass and the React production build and lint checks succeed.

## Completion Status

- Backend persistence, service, API model, endpoint, editor form, and route integration are complete.
- Client-side Unicode-aware character-limit enforcement, pending/error states, accessible toolbar controls, and HTTP(S) link validation are complete.
- Persisted plain text is derived from validated editor JSON rather than trusted from the client projection.
- Feedback form, editor lifecycle, rich-text field, toolbar controls, and emoji picker are separated into focused feature-local modules under the rules in `FE_ARCHITECTURE.md`.
- Focused feedback tests and the full frontend/backend verification matrix pass.

## Update – 2026-07-30

The end-to-end feedback path is complete in the working tree and coordinated with `FRONTEND_TAILWIND_ARCHITECTURE_IMPLEMENTATION_PLAN_20260730.md`. The implementation uses the shared React/Tailwind architecture and feature-local editor components instead of CSS Modules.

## Product Owner Email Notification Update – 2026-07-30

**Timestamp:** **2026-07-30T15:43:02Z (UTC) | 30-07-2026 21:13:02 (IST)**

- Notify `garudagaura@gmail.com` when validated feedback has been persisted.
- Use a dependency-inverted SMTP adapter configured through deployment environment variables; no credentials are committed.
- Include the feedback receipt, reporter identity/email when available, category, title, and trusted plain-text projection.
- Treat notification delivery as non-critical: the persisted Product Owner control-center record remains the source of truth if SMTP is unavailable.
- Cover successful notification and delivery-failure persistence behavior with offline tests.

### Completion Summary

- Added a `FeedbackNotifier` application port and an environment-configured SMTP adapter using the Python standard library.
- Wired notification delivery through `FeedbackService` after persistence and passed the authenticated reporter email from `POST /api/feedback`.
- Added Gmail SMTP defaults to the Render Blueprint while keeping the username and App Password secret.
- Added tests for recipient/message delivery, reporter reply address, invalid port fallback, and persistence during SMTP failure.

## Render Free Email Transport Fix – 2026-07-30

**Timestamp:** **2026-07-30T16:31:00Z (UTC) | 30-07-2026 22:01:00 (IST)**

- Replaced the deployed Gmail SMTP transport with Resend's HTTPS API because Render Free blocks outbound SMTP ports 25, 465, and 587.
- Added explicit missing-configuration and rejected-provider diagnostics while preserving feedback before notification delivery.
- Updated the Render Blueprint to request `RESEND_API_KEY` and a verified `SCREENER_FEEDBACK_EMAIL_FROM` sender.
- Retained the SMTP adapter for non-Render deployments, but the application bootstrap now selects Resend.

## API-First Feedback Retrieval and Editor Overlap Fix – 2026-07-31

**Timestamp:** **2026-07-31T16:18:00Z (UTC) | 31-07-2026 21:48:00 (IST)**

- Removed email notifier registration from the application bootstrap. Feedback submission no longer depends on Gmail, SMTP, Resend, or any other outbound email provider.
- Kept `POST /api/feedback` as the public submission API. It persists validated feedback in `data/feedback.db` before returning the receipt.
- Kept `GET /api/admin/feedback` and `GET /api/admin/feedback/{feedback_id}` as the Product Owner inbox and detail API. These endpoints require Product Owner authentication, so feedback is not exposed publicly.
- Removed the duplicate TipTap CSS pseudo-placeholder. The React placeholder in `RichTextField` is now the sole Details placeholder, preventing overlapping text.

### Completion Summary

- Runtime wiring now uses `FeedbackService` with SQLite persistence only; existing notification adapters remain available as isolated legacy code but are not invoked.
- Removed obsolete Render email environment variables from `render.yaml`.
- Updated the feedback workflow documentation and conversation log to describe the API-backed operational flow.

## Accessibility, Emoji, and Control Center Navigation Fixes – 2026-07-31

**Timestamp:** **2026-07-31T17:00:00Z (UTC) | 31-07-2026 22:30:00 (IST)**

- Added persisted **Decrease text size** and **Increase text size** controls to the shared application header. The root font size changes in bounded 12.5% steps from 87.5% through 125%, so the existing rem-based interface scales consistently for elderly users and the selected value survives reloads.
- Fixed emoji insertion losing the active editor selection by preventing the picker button's mouse-down event from blurring TipTap before insertion. The picker is now constrained to a predictable, viewport-safe grid.
- Fixed first-click control-center navigation crashes by adding Suspense boundaries around lazy route outlets. Users now receive a loading state while a child route loads instead of React error #426.
- Verification target: frontend typecheck, lint, production build, and the existing Python test suite.
