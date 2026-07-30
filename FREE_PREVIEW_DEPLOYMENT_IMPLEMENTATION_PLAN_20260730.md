# Free Preview Deployment Implementation Plan

**Timestamp:** **2026-07-30T06:31:51Z (UTC) | 30-07-2026 12:01:51 (IST)**

## Overview

Prepare stockScreener for a zero-cost public preview that early testers can open over HTTPS. The selected target is a single Render Free web service where FastAPI serves both the JSON API and the compiled React PWA.

## Current State Analysis

- `api.py` already serves `frontend/dist` when present and falls back to `web/`.
- The React client uses same-origin API requests and hash routing, so no cross-origin or static rewrite configuration is needed.
- User accounts, preferences, signing keys, learned content, predictions, and broker settings are stored in SQLite or local files.
- No deployment manifest, container definition, health endpoint, or Python runtime declaration existed.

## Implementation Phases

1. **Deployment packaging**: Build React with Node 22, package FastAPI with Python 3.12, and start Uvicorn on the platform-provided `PORT`.
2. **Render blueprint**: Define one free Docker web service with an HTTP health check.
3. **Operational documentation**: Document dashboard deployment, verification, free-tier behavior, and rollback/removal.
4. **Verification**: Run Python tests, frontend checks/build, Docker build, and a container health request.

## Technical Considerations

- Render Free spins down after 15 idle minutes and can take about one minute to wake.
- Its filesystem is ephemeral. Any tester-created account or other runtime file can disappear on spin-down, restart, or redeploy.
- A paid persistent disk cannot be attached to a Free service. Durable multi-user testing requires migrating SQLite/file state to an external database/object store.
- The Docker image intentionally excludes local secrets and runtime databases.
- The app should run as one Uvicorn worker while SQLite remains in use.

## Success Criteria

- `render.yaml` is accepted as a Render Blueprint.
- The Docker image builds the React production bundle and starts `api:app` on `PORT`.
- `GET /api/health` returns HTTP 200.
- Existing backend tests and frontend build checks pass.
- Documentation makes preview data-loss behavior explicit.

## Completion Summary

- Added a multi-stage production `Dockerfile`, `.dockerignore`, and Render Blueprint.
- Added a lightweight deployment health endpoint.
- Added a deployment guide and expanded runtime-data exclusions.
- Verification results are recorded in the task completion response.
