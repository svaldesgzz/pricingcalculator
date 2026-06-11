---
title: Estimate costs for Azure Extended Zones workloads
description: Use the Azure Extended Zones pricing calculator to estimate monthly costs for VMs, managed disks, public IPs, load balancers, and bandwidth in the Luxembourg and Perth Extended Zones.
author: your-github-handle
ms.author: your-alias
ms.service: azure-extended-zones
ms.topic: how-to
ms.date: 05/19/2026
---

# Estimate costs for Azure Extended Zones workloads

[Azure Extended Zones](overview.md) currently expose a smaller set of services
than the parent Azure region, and they aren't yet integrated into the
[Azure pricing calculator](https://azure.microsoft.com/pricing/calculator/).
This article ships a focused estimator that covers the services available in
each Extended Zone and runs entirely in your browser.

> [!NOTE]
> The estimator is provided for guidance only. It doesn't include taxes,
> Microsoft Azure Consumption Commitment (MACC) discounts, Enterprise
> Agreement pricing, or support plan costs. Validate final figures with your
> Microsoft account team.

## Supported Extended Zones

| Zone | Status | Pricing source |
|---|---|---|
| Luxembourg | Generally available | Latest published meter export |
| Perth | Generally available | **Illustrative** — derived from Luxembourg rates while the verified Perth meter file is finalized |
| Los Angeles | Coming soon | n/a |

## Covered services

- **Virtual Machines** — Bsv2, Dsv5 / Ddsv5, Esv5, NVadsA10v5 series (Linux and Windows)
- **Managed Disks** — Premium SSD v2 (capacity + IOPS + throughput)
- **Public IP addresses** — Basic / Standard / Global, dynamic or static
- **Load Balancer** — Standard SKU (rules + data processed)
- **Bandwidth** — Internet egress (Standard routing)

## Use the calculator

<iframe
  src="./media/pricing-calculator/index.html"
  title="Azure Extended Zones pricing calculator"
  width="100%"
  height="900"
  loading="lazy"
  style="border:1px solid #E1E1E1; border-radius:8px;">
</iframe>

If the embedded calculator doesn't render in your viewer, open it directly:
[Standalone calculator (HTML)](./media/pricing-calculator/index.html).

## Keep prices up to date

The calculator reads a single JSON file, `catalog.json`, that's generated
from the per-region Excel meter exports. To refresh prices:

1. Drop the new export into `pricingcalculator/`.
2. Run:

   ```bash
   python scripts/extract_catalog.py
   python scripts/inline_catalog.py   # re-inlines catalog.json into index.html
   ```

3. Commit the regenerated `data/catalog.json` and `web/index.html`.

No application code changes are required to update pricing or to add a SKU
that already exists in the source meter file.

## Add a new region

When the Perth meter export becomes machine-readable, or when Los Angeles
launches:

1. Produce `data/<region>-pricing.json` using `scripts/extract_catalog.py`
   (extend the script with a `--region` flag if needed).
2. In `data/catalog.json`, set `available: true` and `priceMultiplier: 1.00`
   on the region entry (and remove `isMock` / `mockNotice` / `comingSoon`).
3. Re-run the inline step and commit.

## Related content

- [Azure Extended Zones overview](overview.md)
- [Azure pricing calculator](https://azure.microsoft.com/pricing/calculator/)
- [Azure reservations](/azure/cost-management-billing/reservations/)
