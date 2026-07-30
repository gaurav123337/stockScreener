# Frontend Architecture

**Status:** Normative reference for `frontend/src`
**Stack:** React 18, TypeScript, Vite, React Router, TanStack Query, React Hook Form, TipTap, Tailwind CSS v4

This document defines the rules for adding and changing frontend code. Existing code may contain migration debt; every modified area should move toward these rules, and new code must follow them.

## 1. Module Boundaries

```text
src/
  app/             application composition, providers, routing, layout, global infrastructure
  api/             typed HTTP transport and endpoint definitions
  components/ui/   reusable visual primitives with no feature business logic
  components/      shared domain-neutral components
  features/<name>/ route pages, feature components, feature hooks, feature types
  lib/             pure cross-feature utilities
  types/           shared API and domain contracts
```

- Feature code belongs under its feature folder. A feature must not import another feature's private component or hook.
- `app` composes features; it must not contain feature-specific business rules.
- API modules own transport only. They must not render UI or show toasts.
- Shared UI primitives must remain domain-neutral and must not import from `features` or `api`.
- Import direction is toward lower-level modules: `features -> components/lib/api`, `app -> features`, never the reverse.
- Use the existing `@/*` alias for imports. Use relative imports only inside a feature when the relationship is local and obvious.

## 2. Component Boundaries

- Components must have one clear reason to change: route orchestration, a visual section, or one interaction workflow.
- A route page should coordinate queries, mutations, and feature components. It should not contain a large table, editor toolbar, settings field renderer, or credential form inline.
- Begin decomposition when a component exceeds roughly 150 lines, has more than one independent UI region, or mixes server state with complex local interaction state. The threshold is a signal, not a mechanical rule.
- Extract a component when a block has its own props, loading/error/empty state, keyboard behavior, or repeated markup.
- Extract a hook when state and effects form a cohesive reusable workflow, such as autocomplete, editor lifecycle, or a query/mutation interaction.
- Keep components presentational when possible: pass data and callbacks in, render UI out. Keep API calls and cache invalidation in the route or a feature hook.
- Do not create abstractions solely to reduce line count. A component boundary must improve ownership, testability, or readability.
- Prefer explicit prop interfaces. Avoid `any`, broad index signatures in UI props, and prop bags whose meaning is unclear.

## 3. State and Data Fetching

- Use TanStack Query for server state, cache, loading, error, and invalidation.
- Use local `useState` for transient UI state such as an open menu, selected row, or input draft.
- Do not duplicate query data in local state unless it is intentionally an editable draft.
- Keep query keys stable and descriptive. Mutations must invalidate the smallest affected query scope after success.
- Keep derived values derived during render or in pure helpers; do not synchronize them with effects.
- Effects are for external synchronization only: event listeners, timers, browser APIs, and third-party instances. Always clean up listeners and timers.
- Do not add Redux, a global store, or context for state that belongs to one route or feature.

## 4. Forms and Editors

- Use React Hook Form for multi-field forms and existing controlled state only where a third-party editor or a small interaction requires it.
- Keep validation rules close to the form boundary and validate again at the API/backend boundary.
- Every field needs a visible label or an accessible label, a stable `id`, and an associated error/help description when applicable.
- Submit buttons must have `type="submit"`; non-submit controls inside forms must have `type="button"`.
- Disable submission while a mutation is pending and provide a visible status/error state.
- TipTap configuration and lifecycle belong in a feature hook; editor rendering and toolbar controls belong in feature components.
- Never trust a client-provided derived value when the backend can derive it from the submitted document.

## 5. Accessibility and Interaction

- Prefer semantic HTML (`button`, `nav`, `main`, `form`, headings, lists, table semantics) over clickable generic elements.
- Interactive controls need keyboard access, visible focus, an accessible name, and an appropriate pressed/expanded state.
- Do not use a clickable table row unless keyboard behavior and `aria-expanded` are implemented; prefer a button in the row when the interaction grows more complex.
- Loading, error, and empty states must be distinguishable and should use `role="status"` or `role="alert"` where appropriate.
- Icons are decorative when adjacent text supplies the label; otherwise provide an accessible label and tooltip/title for unfamiliar controls.
- Never rely on color alone to communicate action, error, or selection.

## 6. Tailwind and Styling

- Tailwind v4 is the styling system. Use semantic tokens from `src/styles/global.css` and shared primitives for recurring controls.
- Do not add CSS Modules or component CSS for ordinary layout and presentation.
- TipTap-generated HTML may use the small `.feedback-editor` rules in global CSS because those nodes cannot receive JSX classes.
- Tailwind class strings must be complete static strings. Use explicit maps for dynamic variants; do not interpolate partial class names.
- Keep repeated class combinations in a shared primitive or a local named constant when it materially improves readability.
- Preserve responsive behavior with stable layouts and avoid fixed dimensions that cause text overlap.

## 7. Naming and Files

- Components use PascalCase (`ScanResultsTable.tsx`), hooks use `useX.ts`, pure helpers use descriptive camelCase names, and tests mirror the feature path.
- A page file should be named `<Feature>Page.tsx`; feature-only components belong in `features/<feature>/components`.
- Prefer named exports for feature components and hooks. Default exports are retained for route page compatibility.
- Keep constants and configuration separate from render code when they are reused or domain-significant.
- Comments should explain a non-obvious constraint or decision, not narrate straightforward code.

## 8. Quality Gates

Every frontend change must pass:

```bash
npm run format
npm run typecheck
npm run lint
npm run build
```

Before review, also check:

- The page component still reads as orchestration rather than a markup dump.
- Server state is owned by Query and transient state is owned by the smallest useful component/hook.
- New components have focused props and no feature-boundary violations.
- Loading, error, empty, pending, and keyboard states are covered.
- No CSS Module, inline presentation style, legacy global class, or unsafe dynamic Tailwind class was introduced.
- Tests cover changed pure transformations and high-risk user workflows.