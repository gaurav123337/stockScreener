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
