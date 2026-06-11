# Azure Extended Zones Pricing Calculator — Overview Memory

> Single source of truth across all agents. Update after each phase.

## Project goal
Build a self-contained pricing calculator for **Azure Extended Zones** (currently only Luxembourg + Perth; Los Angeles surfaced as "coming soon"). The calculator must:
- Live in a way that can be pushed to `MicrosoftDocs/azure-docs` as a Markdown article that embeds the HTML (Microsoft Learn supports raw HTML in some pages; we ship a single-file `index.html` plus a Markdown wrapper that includes it via iframe or embedded code-block instructions).
- Read prices from a versioned data file derived from the source Excel exports, so prices can be refreshed without code changes.
- Match the polish level of `calculator.aws` / `azure.microsoft.com/pricing/calculator` for the subset of services Extended Zones offers.

## Source data
| File | Status | Notes |
|---|---|---|
| `20260513 - Luxembourg SKU Pricing May 2026.xlsx` | ✅ Read OK | 6,740 rows. Filtered to `IsLatest=True` + `AvailabilityRegion=Luxembourg` → `data/luxembourg-pricing.json` |
| `20251008 - Perth - Meter Data (Oct 8).xlsx` | ⚠️ DRM-encrypted | Cannot read without password. Backend uses **mock Perth pricing = Luxembourg × 1.05** with a banner stating it is illustrative. Replaceable in `data/perth-pricing.json`. |

## Service scope (Extended Zones)
Sourced from <https://learn.microsoft.com/en-us/azure/extended-zones/overview>. We include only services that appear both in the docs list AND in the Luxembourg meter export:
1. **Virtual Machines** — Bsv2, Dsv5, Ddsv5, Dsv6, Ddsv6, Esv5, Edsv5, Ebsv5, Ebdsv5, Esv6, Edsv6, NVadsA10v5 (curated subset; Linux + Windows variants where present)
2. **Managed Disks** — Premium SSD v2 (capacity, IOPS, throughput)
3. **Load Balancer** — Standard SKU (rules + data processed)
4. **Public IP Addresses** — Basic, Standard, Global (static / dynamic)
5. **Bandwidth** — Internet egress (Standard routing)
6. **Virtual Network** — included free as background context

## Architecture
```
pricingcalculator/
├── data/                          # versioned price data (regenerate from xlsx)
│   ├── luxembourg-pricing.json    # raw filtered dump (6740 rows)
│   ├── perth-pricing.json         # mock (Lux × 1.05) until DRM-protected file is unlocked
│   └── catalog.json               # curated, calculator-ready services + skus + per-hour rates
├── scripts/
│   ├── extract_catalog.py         # reads luxembourg-pricing.json → catalog.json
│   └── inspect.py                 # data-discovery helper used during scoping
├── plan/                          # this folder
│   ├── overview-memory.md         # ← you are here
│   ├── pm-agent-plan.md
│   ├── pm-agent-log.md
│   ├── swe-agent-plan.md
│   ├── swe-agent-log.md
│   ├── design-agent-plan.md
│   ├── design-agent-log.md
│   ├── qa-agent-plan.md
│   └── qa-agent-log.md
├── web/
│   ├── index.html                 # single-file calculator (HTML + CSS + JS inline for embeddability)
│   └── catalog.json               # symlinked/copied at build time from data/catalog.json
├── docs/
│   └── azure-extended-zones-pricing-calculator.md   # azure-docs-ready Markdown wrapper
└── initial-request.md
```

## Status board
| Phase | Agent | Status | Started | Completed |
|---|---|---|---|---|
| 0. Data discovery | PM | ✅ complete | 2026-05-19 | 2026-05-19 |
| 1. Spec & plan files | PM | ✅ complete | 2026-05-19 | 2026-05-19 |
| 2. Backend (catalog + data layer) | SWE | ✅ complete | 2026-05-19 | 2026-05-19 |
| 3. Frontend (UI + calc engine) | Design | ✅ complete | 2026-05-19 | 2026-05-19 |
| 4. QA review | QA | ✅ complete | 2026-05-19 | 2026-05-19 |
| 5. azure-docs Markdown wrapper | SWE | ✅ complete | 2026-05-19 | 2026-05-19 |

## Open issues / follow-ups
- Replace `data/perth-pricing.json` once the Perth Excel file is decrypted (drop a real export in and re-run `scripts/extract_catalog.py --region Perth`).
- Los Angeles: a "Coming soon" region entry is wired in the UI; add a real catalog file when Microsoft publishes the meter data.
- Reserved Instance / Savings Plan pricing exists in the raw data but is intentionally **not** surfaced in v1 — only pay-as-you-go. RI columns are preserved in `catalog.json` so a follow-up can add a term selector.
