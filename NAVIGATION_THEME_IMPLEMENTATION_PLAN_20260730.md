# Navigation and Theme Implementation Plan

**Timestamp:** **2026-07-30T10:28:59Z (UTC) | 30-07-2026 15:58:59 IST**

## Overview

Refine the React application shell so the four core workflows—Recommended, Scan, Train, and Broker—remain directly accessible in the bottom navigation, while secondary destinations move into a hamburger menu. Add a user-controlled light/dark appearance that persists across visits.

## Current State Analysis

- `frontend/src/app/layout/AppLayout.tsx` renders all seven routes in both the desktop rail and the mobile bottom navigation.
- `frontend/src/styles/global.css` defines one dark palette through semantic Tailwind tokens.
- The app has no theme state, browser preference integration, or persisted appearance setting.
- Routes are already centralized in `frontend/src/app/router.tsx`; no route changes are required.

## Implementation Phases

1. Split navigation metadata into four primary destinations and three secondary destinations.
2. Keep primary destinations in the desktop rail and mobile bottom bar; render secondary destinations in an accessible header menu.
3. Add a theme hook that reads/writes local storage, falls back to the operating-system preference, applies the root theme class, and updates browser chrome metadata.
4. Define light and dark semantic color token values in the global stylesheet.
5. Run the frontend formatting, type-checking, linting, and production build gates.

## Technical Considerations

- Navigation remains route-driven with `NavLink`; route URLs and lazy loading remain unchanged.
- The menu uses semantic buttons/navigation, closes after route changes, supports Escape, and reports its expanded state.
- Theme preference is browser-local and independent of authentication, so guest and signed-in users receive consistent behavior without an API change.
- Existing semantic utility classes (`bg-canvas`, `bg-surface`, `text-ink`, and related tokens) allow the palette to change without modifying feature ownership boundaries.

## Success Criteria

- Only Recommended, Scan, Train, and Broker appear in persistent primary navigation.
- Settings, Guide, and Feedback are reachable from the hamburger menu.
- A labeled control switches between light and dark modes.
- The selected theme survives reloads; first-time users inherit their system preference.
- The app remains responsive, keyboard accessible, and passes all existing frontend quality gates.

## Next Steps

- Review the running application on representative mobile and desktop viewports.

## Completion Summary

- Split the application navigation into four persistent primary destinations and three secondary hamburger-menu destinations.
- Added outside-click, route-change, and Escape-key menu dismissal with accessible expanded-state metadata.
- Added a light/dark theme switch that starts from the system preference, persists explicit choices in local storage, updates browser chrome, and applies semantic colors throughout existing feature screens.
- Preserved all route URLs, authentication behavior, PWA installation behavior, and responsive desktop/mobile layouts.
- Validation completed successfully with `npm run format`, `npm run typecheck`, `npm run lint`, `npm run build`, and `git diff --check`.
- No frontend test runner is configured in this repository, so no automated component tests were added.
