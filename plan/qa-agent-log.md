# QA-Agent Log

| Timestamp (UTC) | Status | Task |
|---|---|---|
| 2026-05-19T18:00:00Z | started | Reviewed `qa-agent-plan.md` and inspected the calculator end-to-end. |
| 2026-05-19T18:02:00Z | working | Ran `scripts/qa_check.py` — automated invariants on `data/catalog.json`. |
| 2026-05-19T18:03:00Z | pass | ✓ Every VM SKU has linuxPerHour > 0 and windowsPerHour > 0. |
| 2026-05-19T18:03:00Z | pass | ✓ Every VM SKU windowsPerHour ≥ linuxPerHour. |
| 2026-05-19T18:03:00Z | pass | ✓ 3 regions in order: luxembourg, perth, losangeles. |
| 2026-05-19T18:03:00Z | pass | ✓ Perth priceMultiplier == 1.05, isMock == True. |
| 2026-05-19T18:03:00Z | pass | ✓ 5 services: vm, disk, publicIp, loadBalancer, bandwidth. |
| 2026-05-19T18:04:00Z | pass | ✓ Spot-check: 2 × D4s_v5 Linux × 730 h, Luxembourg → $454.06. |
| 2026-05-19T18:04:00Z | pass | ✓ Spot-check: Premium SSD v2 128 GiB / 3000 IOPS / 125 MB/s → ~$53.44. |
| 2026-05-19T18:04:00Z | pass | ✓ Spot-check: Perth 100 GB egress → $11.34 (1.05× multiplier applied). |
| 2026-05-19T18:05:00Z | pass | ✓ Inline catalog present in `web/index.html` (grep `B2s_v2` matches). |
| 2026-05-19T18:06:00Z | defect-found | The original empty-state had a generic message — assigned to Design. |
| 2026-05-19T18:07:00Z | fixed-by-design | Empty state now reads "No services yet — Pick a service above to start estimating your monthly bill." |
| 2026-05-19T18:08:00Z | defect-found | `fetch('catalog.json')` is blocked under `file://` in Chromium → assigned to SWE. |
| 2026-05-19T18:09:00Z | fixed-by-swe | Added inline `<script type="application/json">` fallback + `scripts/inline_catalog.py`. |
| 2026-05-19T18:10:00Z | defect-found | Perth badge originally said "Mock" — too jargon-y. Assigned to Design. |
| 2026-05-19T18:11:00Z | fixed-by-design | Banner now reads "Illustrative pricing — derived from Luxembourg rates pending verified Perth meter export." |
| 2026-05-19T18:12:00Z | completed | All defects resolved. Sign-off granted. |
