# Product Owner Control Center Implementation Plan

**Timestamp:** **2026-07-30T11:55:43Z (UTC) | 30-07-2026 17:25:43 (IST)**

## Overview

Create a secure Product Owner Control Center that gives authorized product owners one place to manage users, review and triage feedback, publish common application values, and govern other configurable variables. Complete the account journey with email-based registration, sign-in, email verification, forgot-password, and password reset. Correct the feedback editor placeholder that currently overlaps entered text.

## Goal, Deliverables, and Constraints

### Goal

Give the product owner operational visibility and controlled administration without weakening tenant isolation or exposing sensitive runtime configuration.

### Deliverables

- Product-owner dashboard with summary metrics and recent activity.
- User directory with search, filters, account state, role, and safe administrative actions.
- Feedback inbox with detail, status, priority, assignment, internal notes, and audit history.
- Global configuration manager for common defaults and locked organization-wide values.
- Governed registry for other application variables that are safe to edit at runtime.
- Email-first registration, sign-in, verification, forgot-password, and reset-password journeys.
- Feedback editor placeholder fix and UI regression coverage.
- Role-based authorization, audit logs, database migrations, API tests, and frontend tests.

### Constraints

- Preserve the dependency direction in `ARCHITECTURE.md`: presentation to services to domain, with infrastructure implementing domain contracts.
- Product-owner endpoints must use strict authentication; the existing guest fallback must never grant administrative access.
- Never expose or edit secrets, signing keys, broker credentials, filesystem paths, or infrastructure connection strings in the dashboard.
- Keep existing user preferences isolated and define explicit precedence between factory, global, and user values.
- Migrate existing username accounts without silently losing preferences or ownership links.

## Current State Analysis

### Feedback

- `POST /api/feedback` records feedback through `FeedbackService` in `data/feedback.db`.
- Each record contains `feedback_id`, `user_id`, `username`, category, title, TipTap JSON, derived plain text, and creation time.
- The current database contains one `concern` submission as of this plan.
- `FeedbackStore.list_by_user()` exists, but there is no API or UI for a product owner to list or inspect submissions.
- Feedback has no workflow fields such as status, priority, assignee, resolution, or updated timestamp.
- Guest submissions are all attributed to the shared `guest` identity, so they cannot be tied to a distinct person unless contact details or an anonymous session identifier are added.

### Users and Authentication

- Registration and sign-in currently use `username`; no email is stored.
- Passwords allow four characters, and there is no email verification, forgot-password endpoint, reset token, or reset page.
- Signed tokens expire after seven days, but there are no server-side sessions, revocation, password-change invalidation, or role claims checked against a persisted authorization model.
- `UserStore.list_users()` exists, but no protected admin API or user-management UI exposes it.
- There is no role field, account status, last-login timestamp, or audit log.

### Configuration

- `/api/settings` currently edits the calling user's preferences, not product-wide common values.
- Effective values are currently `process config + user overrides`.
- `AppConfig` has a global `user_config.json` mechanism, but it is not exposed through role-protected product-owner APIs and its name is ambiguous in a multi-user product.
- Editable groups currently include data fetching, scoring, risk, knowledge, verification, and the default stock universe.
- Validation exists for known typed settings, but there is no publish workflow, version history, rollback, lock policy, or audit record.

### Feedback Editor Defect

- `frontend/src/styles/global.css` shows the placeholder for `p:first-child:only-child`.
- A non-empty editor can still contain one paragraph, so the placeholder remains visible and overlaps the user's text.
- The fix should use TipTap's empty-editor state or Placeholder extension, not document shape alone.

## Actors and Access Model

| Role                 | Intended access                                                                                                                                                     |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Guest                | Use explicitly permitted public features and submit anonymous feedback; no saved personal configuration unless the product retains guest preferences intentionally. |
| User                 | Manage own profile and preferences, use application features, submit feedback, and optionally see own feedback history.                                             |
| Product Owner        | View all users and feedback, operate the feedback workflow, and manage approved global configuration.                                                               |
| System Administrator | Manage product-owner roles and environment-level operations; may be the same person initially but remains a separate permission boundary.                           |

Use persisted roles and server-side permission checks. Hiding navigation is not authorization. The first product owner should be bootstrapped from a deployment environment variable or one-time CLI command; public registration must always create a normal `user`.

## Product Scope and User Stories

### Epic 1: Product Owner Dashboard

**PO-01:** As a product owner, I can see total users, verified users, active users, new users, open feedback, and overdue feedback so I can assess product health quickly.

**PO-02:** As a product owner, I can navigate from a metric or recent item to a pre-filtered operational view.

Dashboard widgets:

- User totals by status and verification state.
- New registrations for 7 and 30 days.
- Feedback totals by status, category, priority, and age.
- Recent registrations, recent feedback, and recent configuration publications.
- Explicit empty, loading, error, and unauthorized states.

Do not treat sign-in count as product engagement until event tracking is intentionally added. Label metrics according to the data actually collected.

### Epic 2: User Directory and Account Operations

**USR-01:** As a product owner, I can search and filter all registered accounts by email, display name, role, status, and verification state.

**USR-02:** As a product owner, I can inspect account metadata and effective configuration without seeing password hashes, salts, reset tokens, or secrets.

**USR-03:** As a product owner, I can suspend/reactivate an account and trigger a password-reset email with a reason recorded in the audit log.

Required fields include email, normalized email, display name, role, status, verification time, created time, last login time, and last activity time when activity tracking exists. Destructive deletion should be deferred until retention and referential-integrity rules are approved; use suspension first.

### Epic 3: Feedback Inbox and Triage

**FDB-01:** As a product owner, I can list all feedback with server-side pagination, search, and filters for category, status, priority, user, assignee, and date.

**FDB-02:** As a product owner, I can safely inspect formatted feedback and its plain-text representation, user attribution, and submission metadata.

**FDB-03:** As a product owner, I can set status (`new`, `triaged`, `planned`, `in_progress`, `resolved`, `closed`), priority (`low`, `medium`, `high`, `critical`), assignee, and internal notes.

**FDB-04:** As a product owner, I can see every workflow change in a timestamped audit timeline.

Render rich text from a strict allowlist; never inject stored document content as untrusted HTML. Aggregate anonymous guest feedback separately. If follow-up is required from guests, add an optional contact email with explicit consent and retention text rather than implying the shared guest ID identifies them.

### Epic 4: Common Values and Application Variables

**CFG-01:** As a product owner, I can view the effective product defaults, their source, validation rules, and last publication details.

**CFG-02:** As a product owner, I can save a draft, validate changes, review a diff, publish atomically, and roll back to a prior version.

**CFG-03:** As a product owner, I can decide per setting whether the global value is a default that users may override or a locked value enforced for everyone.

Configuration precedence must be explicit:

1. Factory/application defaults.
2. Deployment environment overrides.
3. Published product-owner global values.
4. User preferences, only where the setting is marked `user_overridable`.
5. Locked global values always win over user preferences.

Create a configuration registry with key, section, label, description, data type, default, bounds or allowed values, sensitivity classification, scope, restart requirement, and user-overridable policy. Initially register the existing safe settings in `AppConfig`: scoring thresholds and weights, risk values, data retry/worker values, knowledge limits/extensions, verification horizon, and default universe.

Exclude environment, debug mode, directories, secret keys, email-provider credentials, database paths, broker credentials, and similar operational secrets. Those remain deployment-managed. Unknown keys must be rejected, publication must be transactional, and every version must retain actor, reason, timestamp, before/after values, and schema version.

### Epic 5: Email Account Lifecycle

**AUTH-01:** As a visitor, I create an account with a unique email address, display name, password, and password confirmation.

**AUTH-02:** As a user, I sign in with email and password and receive the same generic error for an unknown email or wrong password.

**AUTH-03:** As a user, I verify ownership through a single-use, expiring email link.

**AUTH-04:** As a user, I request a password reset without the response revealing whether the email exists.

**AUTH-05:** As a user, I reset my password with a single-use, short-lived token; all prior sessions are invalidated.

Minimum controls:

- Normalize email by trimming and lowercasing for lookup; preserve a display form only if needed.
- Validate syntax and enforce a unique database index on normalized email.
- Require a stronger password policy, with at least 8 characters initially and support for longer passphrases.
- Prefer Argon2id through a maintained password library; if migration is staged, support rehash-on-login from existing PBKDF2 records.
- Store only hashes of verification/reset tokens, with purpose, expiry, used time, and request metadata.
- Rate-limit registration, login, resend-verification, and reset requests.
- Add session records or a token-version mechanism for logout-all and reset invalidation.
- Configure an email provider through deployment secrets and keep a development capture adapter for tests.

Existing username accounts need a migration state. Add nullable email fields first, retain `username` as a legacy display identifier, and require existing users to add and verify an email before the username login path is retired. Feedback ownership remains linked by immutable `user_id`.

### Epic 6: Feedback Editor Defect

**UI-01:** As a user, I see instructional placeholder text only while the feedback editor is empty.

Implement the TipTap Placeholder extension or apply the pseudo-element only to the editor's generated empty-state class. Verify typing, clearing, formatted first paragraphs, paste, light/dark themes, narrow mobile, and desktop layouts.

## Proposed Information Architecture

- `Admin Overview`: operational metrics and recent activity.
- `Users`: searchable user table and user detail drawer/page.
- `Feedback`: triage queue and feedback detail view.
- `Configuration`: Draft, Published, History, and Registry views.
- `Audit Log`: filterable history for account, feedback, role, and configuration actions.

Admin navigation must only appear for authorized roles. User-facing `Settings` remains separate and should clearly say which values are inherited, overridden, or locked.

## Data and API Changes

### Data Model

- Extend users with `email`, `normalized_email`, `email_verified_at`, `role`, `status`, `last_login_at`, and `token_version` or equivalent session invalidation data.
- Add `auth_tokens` for hashed verification and reset tokens with type, expiry, use state, and request metadata.
- Extend feedback with workflow status, priority, assignee, updated time, and optional resolution time.
- Add `feedback_events` or a generic audit table for field changes and internal notes.
- Add versioned `global_config_versions` and a single active-version pointer.
- Add immutable `audit_events` with actor, action, target, reason, timestamp, and sanitized change summary.

Use migration files with backups and forward-only schema versions; do not rely on scattered `CREATE TABLE IF NOT EXISTS` statements for production evolution.

### API Surface

- Public/auth: register, login, verify email, resend verification, forgot password, reset password, logout, logout all, and current profile.
- Product owner users: paginated list, detail, suspend/reactivate, and send reset invitation.
- Product owner feedback: paginated list, detail, workflow update, and event timeline.
- Product owner configuration: registry, current version, draft validation, publish, history, diff, and rollback.
- Product owner dashboard: aggregated summary endpoint.
- Product owner audit: paginated, filterable audit events.

All product-owner APIs require strict auth plus role/permission checks, bounded pagination, validated sorting, and redacted response models. Do not return internal `UserRecord` objects.

## Implementation Phases

### Phase 0: Decisions and UX Specification (2-3 days)

- Confirm whether guest access remains and which features require verified email.
- Approve roles, suspension policy, data retention, anonymous feedback follow-up, and which settings may be locked.
- Select transactional email provider and sender domain.
- Produce dashboard, user detail, feedback triage, configuration publish, and auth recovery wireframes.

### Phase 1: Security and Email Identity Foundation (5-8 days)

- Introduce migrations, email identity fields, roles, account status, and secure role bootstrap.
- Add email registration/sign-in compatibility, verification, reset tokens, rate limits, and session invalidation.
- Build email capture adapter and auth pages/routes.
- Add unit and integration tests, including enumeration, expiry, reuse, suspension, and migration cases.

This phase blocks exposing any administrative UI.

### Phase 2: Feedback Visibility and Defect Fix (4-6 days)

- Correct the editor placeholder and add frontend regression coverage.
- Add feedback workflow fields, query repository methods, admin APIs, triage UI, and audit events.
- Add indexes for created time, status, priority, assignee, category, and user as justified by query plans.
- Verify structured-content rendering and tenant attribution.

### Phase 3: User Dashboard and Operations (4-6 days)

- Add dashboard aggregates, user directory, account detail, and suspension/reactivation.
- Add server-side pagination, filters, empty/error states, and audit history.
- Distinguish registered users from the shared guest identity in metrics.

### Phase 4: Governed Global Configuration (6-9 days)

- Implement the typed registry, versioned store, precedence resolver, draft validation, publish, and rollback.
- Build configuration source indicators and locked/inherited states in user settings.
- Add concurrency protection so two product owners cannot overwrite each other's draft unknowingly.
- Test global defaults, permitted user overrides, locked values, rollback, restart persistence, and invalid publications.

### Phase 5: Hardening and Release (3-5 days)

- Run security review, accessibility checks, migration rehearsal, backup/restore test, and performance tests.
- Add operational monitoring for auth email failures, elevated 4xx/5xx rates, feedback queue age, and config publication failures.
- Release behind admin feature flags, seed the initial product owner, validate production email delivery, and document rollback.

Estimated delivery: 22-34 engineering days after product decisions and UX approval, depending on email-provider and migration complexity.

## Acceptance Criteria

### Administration

- A normal user or guest receives `403` or `401` from every product-owner API even when calling it directly.
- A product owner can find every registered account through paginated search and filters without receiving secret fields.
- Suspension immediately prevents new authenticated access and invalidates existing sessions.
- Every privileged mutation produces an immutable audit event containing the actor and reason.

### Feedback

- Every stored feedback record is visible in the authorized inbox, including the existing submission after migration.
- Product owners can filter, assign, prioritize, and move feedback through the approved workflow.
- Rich content is rendered through a safe allowlist and plain text remains searchable.
- The placeholder disappears immediately after typing and reappears only when the editor is empty, with no overlap at supported viewports.

### Configuration

- Product owners can validate and preview a diff before publishing.
- A publication is atomic, versioned, audited, and survives application restart.
- User-overridable values follow the published default until overridden; locked values cannot be changed by a user or guest.
- Invalid, unknown, sensitive, and out-of-range values cannot be published.
- A product owner can roll back to a prior valid version without direct database or file editing.

### Authentication

- New accounts are uniquely identified by normalized email and cannot self-assign an elevated role.
- Verification and reset links expire, are single use, and are stored only as token hashes.
- Forgot-password responses do not disclose account existence.
- Password reset invalidates prior sessions, and suspended accounts cannot sign in or reset into an active session.
- Existing accounts retain their `user_id`, preferences, and feedback links throughout migration.

### Quality Gates

- Backend unit/integration tests, frontend typecheck, lint, production build, and focused UI tests pass.
- Authorization tests cover every admin endpoint with guest, user, product-owner, expired-token, and suspended-account contexts.
- Migration is rehearsed against copies of the current `users.db` and `feedback.db`, with verified rollback and record counts.

## KPIs After Release

- Feedback acknowledgment time and median time from `new` to `triaged`.
- Open feedback aging by priority and category.
- Registration completion and email-verification completion rates.
- Password-reset request-to-success rate and email delivery failure rate.
- Active versus suspended registered accounts, clearly excluding the shared guest account.
- Configuration publication success/rollback counts and settings-related support incidents.

## Risks and Mitigations

| Risk                                                 | Mitigation                                                                                           |
| ---------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Admin data exposure                                  | Dedicated redacted DTOs, strict RBAC dependency, endpoint authorization tests, and audit logging.    |
| Existing username users cannot sign in after cutover | Staged nullable-email migration and temporary legacy login until email claim is complete.            |
| Global changes unexpectedly alter user results       | Preview impact, typed validation, versioning, lock semantics, feature flag, and one-click rollback.  |
| Reset links are stolen or replayed                   | Short expiry, hashed tokens, single use, rate limiting, and session invalidation.                    |
| Guest metrics or attribution are misleading          | Report guest separately and never count the shared guest row as a registered person.                 |
| SQLite write contention as admin usage grows         | Short transactions, WAL, indexes, bounded queries, load tests, and a documented path to managed SQL. |

## Product Owner Decisions Required

1. Which application features require sign-in, and which additionally require verified email?
2. Should guest feedback remain anonymous, request optional contact email, or require an account?
3. Can product owners promote other product owners, or is that reserved for system administrators?
4. Which settings are user-overridable, globally locked, or deployment-only?
5. What are the retention and deletion policies for users, feedback, audit events, and reset metadata?
6. Which feedback statuses, priorities, SLA targets, and assignment model should be used?
7. Which email provider, sender domain, and production support mailbox are approved?

## Recommended Backlog Order

1. Approve the seven product decisions and wireframes.
2. Deliver migrations, persisted roles, strict authorization, and email identity/recovery.
3. Fix the feedback placeholder and expose the feedback triage inbox.
4. Deliver user dashboard and safe account operations.
5. Deliver versioned global configuration and lock/override behavior.
6. Complete security, accessibility, migration, and operational-readiness gates before enabling the control center in production.
