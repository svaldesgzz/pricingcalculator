"""
Fetch live pricing from the public Azure Pricing API.

The Azure Retail Pricing API is public and requires no authentication:
  https://prices.azure.com/api/retail/prices

This script demonstrates how to query the API and transform the response into
the catalog.json format. This can serve as an alternative to xlsx-based extraction,
or be integrated into the HTML page as a live data source.

Docs: https://learn.microsoft.com/en-us/azure/cost-management-billing/cost-management-automation/price-partner-sdk/
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"

REGIONS = [
    {"id": "luxembourg", "name": "Luxembourg"},
    {"id": "perth", "name": "Perth"},
    {"id": "losangeles", "name": "Los Angeles"},
]

# Strictly limit API queries to the three Extended Zone parent regions.
# UI labels stay as Luxembourg / Perth / Los Angeles.
ARM_REGION_TO_ID = {
    "westeurope": "luxembourg",
    "australiaeast": "perth",
    "westus": "losangeles",
}
ARM_REGION_TO_LOCATION = {
    "westeurope": "EU West",
    "australiaeast": "AU East",
    "westus": "US West",
}
TARGET_REGION_FILTER = (
    "(armRegionName eq 'westeurope' or "
    "armRegionName eq 'australiaeast' or "
    "armRegionName eq 'westus')"
)

SERVICE_ICON = {
    "Virtual Machines": "vm",
    "Storage": "disk",
    "Backup": "disk",
    "Virtual Network": "publicIp",
    "Load Balancer": "lb",
    "Azure Firewall": "lb",
    "Azure DDOS Protection": "publicIp",
    "ExpressRoute": "bandwidth",
    "Azure Kubernetes Service": "vm",
    "Azure Site Recovery": "disk",
}

ALLOWED_SERVICES = {
    "Virtual Machines",
    "Azure Kubernetes Service",
    "Storage",
    "Backup",
    "Azure Site Recovery",
    "ExpressRoute",
    "Virtual Network",
    "Load Balancer",
    "Azure Firewall",
    "Azure DDOS Protection",
}


def _vm_series_token(product_name: str) -> str:
    name = (product_name or "").strip()
    if name.lower().startswith("virtual machines "):
        name = name[len("virtual machines "):].strip()
    parts = name.split()
    return parts[0] if parts else ""


def is_allowed_vm(product_name: str) -> bool:
    token = _vm_series_token(product_name)
    if not token:
        return False
    low = token.lower()
    if low.startswith("nvadsa10"):
        return True
    if low.startswith(("internal", "gen", "cloud")):
        return False
    first = token[0].upper()
    return first in {"A", "B", "D", "E", "F"}


def unit_type_for_meter(meter: str) -> str:
    m = (meter or "").lower()
    if "hour" in m or "/hr" in m:
        return "hour"
    if "month" in m or "/mo" in m:
        return "month"
    if "day" in m:
        return "day"
    return "unit"


def query_pricing_api(filter_expr: str) -> tuple[Optional[list[dict]], int, float]:
    """
    Query the public Azure Pricing API.
    Returns paginated results as a flat list.
    
    OData filter examples:
      - serviceName eq 'Virtual Machines'
      - armSkuName eq 'Standard_D4s_v5'
      - priceType eq 'Consumption'
      - region eq 'luxbg'
    """
    endpoint = "https://prices.azure.com/api/retail/prices"
    results = []
    url = endpoint + "?" + urlencode({"$filter": filter_expr})
    request_count = 0
    start = time.perf_counter()
    
    while url:
        try:
            print(f"Fetching {url[:100]}...", file=sys.stderr)
            request_count += 1
            with urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read())
                results.extend(data.get("Items", []))
                url = data.get("NextPageLink", None)
        except Exception as e:
            print(f"ERROR fetching {url[:80]}: {e}", file=sys.stderr)
            return None, request_count, time.perf_counter() - start
    
    return results, request_count, time.perf_counter() - start


def build_catalog_from_api() -> Optional[dict]:
    """
    Fetch live pricing from the Azure API and build catalog.json structure.
    
    Returns None if any fetch fails. The HTML page will fall back to the inlined
    catalog in that case.
    """
    services: dict[str, list[dict]] = {}
    total_requests = 0
    total_seconds = 0.0
    filtered_out_non_retail_or_inactive = 0
    filtered_out_wrong_region_fields = 0
    
    # Query for each extended zone service.
    for svc_name in sorted(ALLOWED_SERVICES):
        filter_str = (
            f"serviceName eq '{svc_name}' and "
            f"type eq 'Consumption' and "
            f"{TARGET_REGION_FILTER}"
        )
        print(f"\n{svc_name}:", file=sys.stderr)
        
        items, req_count, elapsed = query_pricing_api(filter_str)
        total_requests += req_count
        total_seconds += elapsed
        if items is None:
            return None
        
        print(f"  Fetched {len(items)} items in {elapsed:.1f}s ({req_count} requests)", file=sys.stderr)
        
        # Parse items into SKUs.
        for item in items:
            product_name = item.get("productName", "")
            sku_name = item.get("armSkuName", "")
            meter_name = item.get("meterName", "")
            item_type = item.get("type", "")
            arm_region = (item.get("armRegionName", "") or "").lower()
            location = (item.get("location", "") or "")
            rate = float(item.get("retailPrice", 0))
            effective_start = item.get("effectiveStartDate", "")

            # Active retail meters only.
            if item_type != "Consumption":
                filtered_out_non_retail_or_inactive += 1
                continue
            if effective_start:
                try:
                    start_dt = datetime.fromisoformat(effective_start.replace("Z", "+00:00"))
                    if start_dt > datetime.now(timezone.utc):
                        filtered_out_non_retail_or_inactive += 1
                        continue
                except ValueError:
                    filtered_out_non_retail_or_inactive += 1
                    continue
            if rate < 0:
                filtered_out_non_retail_or_inactive += 1
                continue
            
            # Skip anything outside the strict 3-region allowlist.
            region_id = ARM_REGION_TO_ID.get(arm_region)
            if not region_id:
                continue

            # Require location consistency with selected region mapping.
            expected_location = ARM_REGION_TO_LOCATION.get(arm_region)
            if expected_location and location != expected_location:
                filtered_out_wrong_region_fields += 1
                continue
            
            # VM series filter: only A/B/D/E/F + NVadsA10v5.
            if svc_name == "Virtual Machines" and not is_allowed_vm(product_name):
                continue
            
            unit_type = unit_type_for_meter(meter_name)
            
            # Upsert entry.
            entry = None
            for e in services.setdefault(svc_name, []):
                if (e["productName"] == product_name and e["skuName"] == sku_name
                    and e["meterType"] == meter_name):
                    entry = e
                    break
            if not entry:
                entry = {
                    "productName": product_name,
                    "skuName": sku_name,
                    "meterType": meter_name,
                    "unitType": unit_type,
                    "rates": {},
                }
                services[svc_name].append(entry)
            
            entry["rates"][region_id] = rate
    
    # Sort and structure.
    for items in services.values():
        items.sort(key=lambda e: (e["productName"], e["skuName"], e["meterType"]))
    
    service_order = sorted(services.keys(), key=lambda s: -len(services[s]))
    catalog_services = []
    for name in service_order:
        catalog_services.append({
            "id": re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"),
            "name": name,
            "icon": SERVICE_ICON.get(name, "vm"),
            "skuCount": len(services[name]),
            "skus": services[name],
        })
    
    print(
        f"\nPricing API totals: {total_requests} requests in {total_seconds:.1f}s",
        file=sys.stderr,
    )
    print(
        f"Filtered non-retail/inactive: {filtered_out_non_retail_or_inactive}; "
        f"filtered region mismatches: {filtered_out_wrong_region_fields}",
        file=sys.stderr,
    )

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataSource": {
            "kind": "api",
            "label": "Fresh API data",
            "generator": "scripts/fetch_pricing_api.py",
            "api": {
                "endpoint": "https://prices.azure.com/api/retail/prices",
                "filter": "type=Consumption and armRegionName in [westeurope,australiaeast,westus]",
            },
        },
        "currency": "USD",
        "regions": REGIONS,
        "services": catalog_services,
    }


def main():
    print("Fetching live pricing from Azure Pricing API...", file=sys.stderr)
    catalog = build_catalog_from_api()
    
    if not catalog:
        print("FAILED to fetch from API. Keeping existing fallback.", file=sys.stderr)
        return 1
    
    total_skus = sum(s["skuCount"] for s in catalog["services"])
    print(f"\nCatalog built: {len(catalog['services'])} services, {total_skus:,} SKU entries", file=sys.stderr)
    for s in catalog["services"]:
        print(f"  {s['name']}: {s['skuCount']}", file=sys.stderr)
    
    out = WEB_DIR / "catalog-live.json"
    out.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    print(f"\nWrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

