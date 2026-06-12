# ASAGUS v3 Frontend Audit & Fix Report

Date: 2026-06-03  
Scope: `frontend/app/page.tsx`, `frontend/app/globals.css`, shared frontend widgets, and API client behavior.

## CTO-Level Findings

| Area | Issue Found | Fix Applied |
| --- | --- | --- |
| Navigation | Tabs were internal state only; `/run` returned a 404 and users could not deep-link or refresh into a tab. | Added hash-addressable tabs such as `/#run`, `/#pipeline`, and `/#records`. |
| Run workflow | The Run page showed too many expert controls at once, making the primary job-start workflow hard to scan. | Added a readiness cockpit, preset cards, and collapsed advanced controls. |
| Error handling | Backend network failures displayed as a generic `Failed to fetch` pill that was truncated in the header. | Added a dismissible alert banner and API errors that include the backend URL/path. |
| Visual hierarchy | Metrics, overview cards, forms, and side panels all had similar visual weight. | Strengthened spacing, card hierarchy, status treatments, and focus states. |
| Data states | Empty job, event, record, and layer views looked blank or weak. | Added reusable empty states and selected-job highlighting. |
| Tables | Long URLs could make tables hard to scan. | Added truncation and a framed scrollable table surface. |
| Mobile | The app was usable but cramped and visually flat. | Improved responsive grid behavior, sidebar wrapping, switches, and stacked cards. |
| Destructive actions | Delete/clear buttons were mostly text-only and easy to miss. | Added destructive action icons and clearer button styling. |
| Jobs operations | Job history had no operator-side filtering or sorting. | Added filter and sort controls for status/query/location/preset, newest, status, and record count. |
| Records operations | Records had no quick way to narrow or order large local datasets. | Added client-side filter and sorting by quality, confidence, name, and city. |
| Backend connection | Backend failure state was reactive only and did not offer retry from the status surface. | Added a backend connection strip with service count and retry action. |
| Repeated sessions | Run form values reset on reload. | Added local-storage persistence for run-form values and real fetch/discovery switches. |

## Current Verification

- `npm run build` passed.
- `npx tsc --noEmit` passed after the Next build regenerated `.next/types`.
- Headless Chrome screenshots were captured for desktop and mobile at `/#run`.
- Follow-up verification: `npx tsc --noEmit` passed after adding filters, connection retry, and run-form persistence.

## Remaining Product Work

- Split `page.tsx` into route-level sections/components; it is still too large for long-term maintenance. This should be done as a dedicated refactor so behavior does not drift while moving code.
- Add Playwright-based visual regression tests once the project includes a browser test dependency.
- Add richer record operations: CSV export, column visibility, saved filters, and bulk selection.
- Add richer job operations: event search, event-type filters, and quick links from job events to archived evidence.
