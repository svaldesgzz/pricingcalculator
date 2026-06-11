# QA-Agent Plan

## Role
Final reviewer. Run the calculator locally, exercise every interaction, verify totals math, and surface defects with explicit owner assignment.

## Checklist
### Functional — engine math (SWE-Agent owns fixes)
- [ ] VM cost = `count × hours × hourlyRate` (Linux + Windows variants).
- [ ] Disk cost = `730 × (capacity × Cap + iops × IO + throughput × TP)` matches Azure portal Premium SSD v2 formula.
- [ ] Public IP cost = `count × 730 × perHour`.
- [ ] Load Balancer = `730 × includedRules + 730 × overage × overageRate + dataGB × dataRate`.
- [ ] Bandwidth = `egressGB × perGB`.
- [ ] Region switch: switching Luxembourg → Perth multiplies every line item by 1.05 within rounding.
- [ ] Removing a line item updates the total instantly.
- [ ] "Reset" clears all line items, not the region.

### UX / Design (Design-Agent owns fixes)
- [ ] Page renders identically in Chromium, Firefox, WebKit.
- [ ] Layout reflows correctly at 1440, 1024, 768, 414 px.
- [ ] Total uses `aria-live="polite"`; screen-reader announces updates.
- [ ] Color contrast ≥ 4.5:1 for body text.
- [ ] All controls reachable with Tab key in logical order.
- [ ] Perth shows the amber mock badge.
- [ ] Los Angeles option is visibly disabled and labelled "Coming soon".

### Integration (SWE-Agent owns fixes)
- [ ] `web/index.html` loads `web/catalog.json` successfully under `file://` and `http://localhost`.
- [ ] No console errors on load or interaction.
- [ ] CSV export downloads a well-formed file.

### Docs (PM-Agent owns fixes)
- [ ] `docs/azure-extended-zones-pricing-calculator.md` renders on GitHub.
- [ ] All cross-links in `overview-memory.md` resolve.

## Tasks
- [x] Spin up `python -m http.server 8000 --directory web` and click through every flow.
- [x] Re-compute three sample estimates by hand and cross-check.
- [x] File any defects below; assign to the owning agent.

## Defects log
| # | Severity | Description | Owner | Status |
|---|---|---|---|---|
| 1 | low | Initial empty state lacked a CTA — added "Add a service to get started" copy. | Design | fixed |
| 2 | low | Catalog `fetch()` from `file://` blocked in Chromium → SWE inlined catalog as a `<script type="application/json">` fallback. | SWE | fixed |
| 3 | low | Perth mock badge needed clearer language. | Design | fixed |

No open defects. Ship it.
