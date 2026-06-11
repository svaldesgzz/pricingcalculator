# Design-Agent Plan

## Role
Own the visual + interaction design of the calculator. The bar: feel native alongside `azure.microsoft.com/pricing/calculator` while taking the clarity cues from `calculator.aws`.

## Principles
1. **Visual cohesion with the Microsoft Learn / Azure brand.** Fluent UI tokens — Segoe UI Variable / system stack, Azure blue (`#0078D4`) as primary, neutral surfaces, restrained shadows.
2. **Two-pane layout, progressive disclosure.** Left: service catalog + configured line items. Right: sticky cost summary that updates live.
3. **One canonical action per screen.** "Add service" is the only primary button until items exist; then "Get monthly estimate" is implicit (the summary).
4. **Zero-jank interactions.** All numeric inputs validate inline; totals update on every keystroke without layout shift.
5. **A11y.** Sufficient contrast (WCAG AA), keyboard reachable, semantic landmarks, ARIA-live total.
6. **No external CSS/JS dependencies.** The whole page must render offline so it works inside an azure-docs iframe.

## Layout
```
┌──────────────────────────────────────────────────────────────────┐
│  Header: logo · "Azure Extended Zones — pricing calculator"      │
│          Region:  ◖ Luxembourg ▾ ◗     [ Perth: mock badge ]     │
├────────────────────────────────────┬─────────────────────────────┤
│  ① Add service (chip grid)         │   Estimated monthly cost   │
│    [VM] [Disk] [IP] [LB] [BW]      │      $ 1,234.56  USD       │
│                                    │  ──────────────────────    │
│  ② Configured items (cards)        │  Per line                  │
│    ┌──────────────────────────┐    │   VM × 2  ...... $876.00   │
│    │ Virtual Machine          │    │   Disk    ......  $58.40   │
│    │ SKU, OS, count, hours    │    │   ...                      │
│    │ Subtotal · trash         │    │  ──────────────────────    │
│    └──────────────────────────┘    │  [ Export as CSV ]         │
│                                    │  [ Reset estimate ]        │
└────────────────────────────────────┴─────────────────────────────┘
Footer: data source · last-updated date · disclaimer
```

Color palette
- `--azure-blue-600: #0078D4` primary
- `--azure-blue-700: #106EBE` primary hover
- `--surface-0: #FAFAFA` body
- `--surface-1: #FFFFFF` cards
- `--ink-1: #1B1B1B` primary text
- `--ink-2: #616161` secondary text
- `--stroke: #E1E1E1` borders
- `--success: #107C10`
- `--warning: #FFB900` (Perth mock badge)
- `--danger:  #D13438` (delete affordances)
- Radius `8px`, shadow `0 1px 2px rgba(0,0,0,.06), 0 4px 8px rgba(0,0,0,.04)`

Typography
- `font-family: "Segoe UI Variable Text", "Segoe UI", system-ui, -apple-system, sans-serif;`
- Sizes (rem): 0.75, 0.875, 1, 1.125, 1.5, 2 — strict scale.

Motion
- 120 ms `cubic-bezier(.2,.8,.2,1)` on interactive states, nothing longer.

## Tasks
- [x] Define design tokens (CSS custom properties).
- [x] Build header with region picker (incl. coming-soon + mock badge).
- [x] Service-chip grid using a 5-up CSS grid with icon + label.
- [x] Reusable line-item card component.
- [x] Sticky right-hand cost summary, `aria-live="polite"`.
- [x] Empty state ("Add a service to get started").
- [x] Responsive: stacks at <960 px, single-column at <640 px.
- [x] Print stylesheet (so the estimate prints cleanly).

## Hand-off
QA reviews the whole experience next.
