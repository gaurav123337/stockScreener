# Filters, Checkboxes, and Knowledge Base Fix Implementation Plan

**Timestamp:** **2026-07-30T10:55:56Z (UTC) | 30-07-2026 16:25:56 (IST)**

## Overview

Restore the complete predefined scan filter selection, make boolean settings controls visually prominent, and prevent the knowledge-base viewer from failing when its backing Markdown file is absent in a deployment.

## Current State Analysis

- `frontend/src/features/scan/ScanPage.tsx` falls back to an empty filter list when `/api/filters` is unavailable, leaving only the `All` option.
- The frontend filter type uses `desc`, while `screener/services/filter_service.py` returns `description`.
- `frontend/src/features/settings/components/SettingsSectionCard.tsx` treats every non-number setting as text; boolean settings need a dedicated checkbox control.
- `/api/knowledge` works with the local checked-in file, but deployments can start without that file. The persistence layer should define a stable empty-state response.

## Implementation Phases

1. Add a frontend definition of the nine built-in filters and use it while filter metadata is loading or unavailable.
2. Correct the filter response contract and let the API response replace the fallback when available.
3. Render boolean settings using a stable, high-contrast native checkbox with explicit checked and focus states.
4. Make `MarkdownKnowledgeStore.get_content()` return an empty knowledge base when the Markdown file is absent, including a race where it disappears before reading.
5. Add focused backend tests and run frontend type, lint, and production-build checks.

## Technical Considerations

- The backend remains authoritative when `/api/filters` succeeds; fallback definitions only cover built-in filters.
- Checkbox values continue through `react-hook-form` as booleans, preserving settings patch semantics.
- Missing knowledge is a valid empty state. Permission and decoding failures remain errors and continue through structured API error handling.
- Existing uncommitted theme and component changes are preserved.

## Success Criteria

- All nine predefined filters remain visible during loading and API failures.
- Filter descriptions populate tooltips from the actual backend field.
- Boolean settings appear as clearly bordered, checked/unchecked controls in light and dark themes.
- `/api/knowledge` returns HTTP 200 with empty content when the knowledge file does not exist.
- Frontend checks and focused backend tests pass.

## Next Steps

- Implement the focused frontend and persistence changes.
- Verify behavior through automated checks and review the resulting diff.
