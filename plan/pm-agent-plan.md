# PM-Agent Plan

## Role
Research the problem space, scope the work, decompose into agent phases, and own the spec.

## Inputs
- `initial-request.md`
- Two Excel exports (Luxembourg, Perth)
- Azure Extended Zones overview: <https://learn.microsoft.com/en-us/azure/extended-zones/overview>
- AWS calculator (UX inspiration): <https://calculator.aws/#/addService>
- Azure pricing calculator (UX inspiration): <https://azure.microsoft.com/en-us/pricing/calculator/>

## Definition of done
1. Excel data shape inventoried; a JSON dump exists per region.
2. A curated, calculator-ready service catalog spec is defined (which services, which SKUs, which meters).
3. Each downstream agent (SWE, Design, QA) has a focused plan file with explicit deliverables and "do-not-touch" boundaries.
4. `overview-memory.md` reflects current status.

## Tasks
- [x] Read `initial-request.md`; identify must-haves vs nice-to-haves.
- [x] Confirm Luxembourg Excel is parseable; confirm Perth is DRM-encrypted and decide mock strategy.
- [x] Enumerate the Extended-Zones service subset that intersects what is present in the Luxembourg meters.
- [x] Decide deployment shape: **single-file `index.html`** loading `catalog.json` at runtime, wrapped by a Markdown article suitable for `azure-docs`.
- [x] Write `swe-agent-plan.md`, `design-agent-plan.md`, `qa-agent-plan.md`.
- [x] Write `overview-memory.md`.

## Scoping decisions (rationale)
- **Pay-as-you-go only in v1.** RI / Savings Plan / Spot pricing is in the source data but multiplies the SKU count ~5×. Surface a "Term" selector in v2.
- **Curated VM list, not all 5,900 rows.** Customers care about ~30 commonly used SKUs (B, D, Ds_v5/v6, Es_v5/v6, NV). The raw dump stays available for re-extraction.
- **Mock Perth pricing.** The user explicitly said "backend with mock data for now". Perth file is DRM-locked — we generate `data/perth-pricing.json` by scaling Luxembourg by 1.05 and clearly badge the UI ("Illustrative — awaiting verified Perth meter data").
- **Los Angeles** is a third Extended Zone but no data is available — show in the region dropdown as disabled with "Coming soon" tag.
- **azure-docs format.** Microsoft Learn renders limited HTML inline; we ship `docs/azure-extended-zones-pricing-calculator.md` that explains the calculator and includes the live `index.html` as a relative-path iframe (works when the repo is hosted as static content), plus a fallback link to the standalone HTML.

## Hand-off
SWE-Agent picks up next; see `swe-agent-plan.md`.
