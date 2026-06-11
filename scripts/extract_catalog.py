"""
Build catalog.json by reading the raw meter-list xlsx files for all three
Azure Extended Zones (Luxembourg, Perth, Los Angeles) and merging them into
a single generic catalog the calculator can render.

The catalog shape is intentionally generic: every (service, product, sku,
meter) tuple becomes one entry with a per-region rate map. The UI groups
entries by serviceName and shows a searchable picker per service tile.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
WEB_DIR = ROOT / "web"

LUX_XLSX = ROOT / "20260513 - Luxembourg SKU Pricing May 2026.xlsx"
PERTH_LA_XLSX = ROOT / "20260519 - Perth + LA - Meter List (May19).xlsx"

REGIONS = [
    {"id": "luxembourg", "name": "Luxembourg"},
    {"id": "perth", "name": "Perth"},
    {"id": "losangeles", "name": "Los Angeles"},
]
REGION_LABEL_TO_ID = {
    "Luxembourg": "luxembourg",
    "Perth": "perth",
    "Los Angeles": "losangeles",
}

SERVICE_ICON = {
    "Virtual Machines": "vm",
    "Storage": "disk",
    "Backup": "disk",
    "Bandwidth": "bandwidth",
    "Virtual Network": "publicIp",
    "Load Balancer": "lb",
    "Application Gateway": "lb",
    "Azure Firewall": "lb",
    "Azure DDOS Protection": "publicIp",
    "ExpressRoute": "bandwidth",
    "Azure Kubernetes Service": "vm",
    "Azure Site Recovery": "disk",
    "Cloud Services": "vm",
    "NAT Gateway": "publicIp",
    "Network Watcher": "publicIp",
    "Specialized Compute": "vm",
}

# Azure Extended Zones service allowlist.
# Source: https://learn.microsoft.com/azure/extended-zones/overview
# Only services explicitly listed in the "Available Azure services and features"
# table are included. Services present in the source xlsx but NOT in the table
# (e.g. Application Gateway, NAT Gateway, Network Watcher, Bandwidth, Cloud
# Services, Specialized Compute) are intentionally excluded.
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

# For Virtual Machines the Extended Zones table only lists general-purpose
# A, B, D, E, F series plus the NVadsA10 v5 GPU series. Everything else
# (Internal GPGen8, Gen7 LI, etc.) is excluded.
_VM_SERIES_RE = re.compile(
    r"^(?:NVadsA10v5|[ABDEF](?:[a-z]*v?\d*|S(?:v\d+)?)?(?:\s|$))",
    re.IGNORECASE,
)


def _vm_series_token(product_name: str) -> str:
    name = (product_name or "").strip()
    prefix = "Virtual Machines "
    if name.lower().startswith(prefix.lower()):
        name = name[len(prefix):].strip()
    parts = name.split()
    return parts[0] if parts else ""


def is_allowed_vm(product_name: str) -> bool:
    token = _vm_series_token(product_name)
    if not token:
        return False
    low = token.lower()
    if low.startswith("nvadsa10"):
        return True
    # Reject known non-allowed series tokens explicitly.
    if low.startswith(("internal", "gen", "cloud")):
        return False
    # Series token must start with A, B, D, E, or F.
    first = token[0].upper()
    return first in {"A", "B", "D", "E", "F"}


def _read_xlsx(path: Path) -> pd.DataFrame:
    """Copy first to bypass file locks (Excel may keep the file open)."""
    tmp = ROOT / f"_tmp_{path.stem}.xlsx"
    shutil.copyfile(path, tmp)
    try:
        df = pd.read_excel(tmp)
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
    return df


def load_all_rows() -> pd.DataFrame:
    """Load all latest rows for our 3 regions (both OnDemand and ReservedInstance)."""
    frames = []
    for path in (LUX_XLSX, PERTH_LA_XLSX):
        if not path.exists():
            print(f"WARNING: {path.name} not found, skipping", file=sys.stderr)
            continue
        df = _read_xlsx(path)
        frames.append(df)
    if not frames:
        raise RuntimeError("No source xlsx files could be read")
    df = pd.concat(frames, ignore_index=True, sort=False)
    df = df[df["IsLatest"] == True]  # noqa: E712
    df = df[df["AvailabilityRegion"].isin(REGION_LABEL_TO_ID)]
    df = df.dropna(subset=["MeterType"])
    return df


def unit_type_for_meter(meter: str) -> str:
    m = (meter or "").lower()
    if "hour" in m or "/hr" in m:
        return "hour"
    if "month" in m or "/mo" in m:
        return "month"
    if "day" in m:
        return "day"
    return "unit"


def build_catalog(df: pd.DataFrame) -> dict:
    # Partition: PAYG rows (OnDemand+Standard) drive the catalog skeleton + rates.
    payg = df[(df["SalesMotion"] == "OnDemand") & (df["RateType"] == "Standard")]
    payg = payg.dropna(subset=["CurrentRate"])
    ri = df[df["SalesMotion"] == "ReservedInstance"].copy()
    ri = ri.dropna(subset=["RIDiscount"])

    # PAYG rate per (svc, prod, sku, meter, region): max within group.
    payg_grouped = (
        payg.groupby(
            ["ServiceName", "ProductName", "SkuName", "MeterType", "AvailabilityRegion"],
            dropna=False,
        )
        .agg(
            CurrentRate=("CurrentRate", "max"),
            SP1Y=("SavingsPlanOneYearDiscount", "max"),
            SP3Y=("SavingsPlanThreeYearsDiscount", "max"),
        )
        .reset_index()
    )

    # RI discount per (svc, prod, sku, meter, region, duration): max.
    ri_grouped = (
        ri.groupby(
            ["ServiceName", "ProductName", "SkuName", "MeterType",
             "AvailabilityRegion", "ReservationDuration"],
            dropna=False,
        )["RIDiscount"]
        .max()
        .reset_index()
    )

    # Pivot regions onto columns for each metric.
    def _pivot(frame, value_col):
        return frame.pivot_table(
            index=["ServiceName", "ProductName", "SkuName", "MeterType"],
            columns="AvailabilityRegion",
            values=value_col,
            aggfunc="max",
        )

    rate_pv = _pivot(payg_grouped, "CurrentRate")
    sp1y_pv = _pivot(payg_grouped, "SP1Y")
    sp3y_pv = _pivot(payg_grouped, "SP3Y")

    # RI: pivot per duration separately.
    ri1y_pv = _pivot(ri_grouped[ri_grouped["ReservationDuration"] == "1 Year"], "RIDiscount")
    ri3y_pv = _pivot(ri_grouped[ri_grouped["ReservationDuration"] == "3 Years"], "RIDiscount")

    services: dict[str, list[dict]] = {}
    for key in rate_pv.index:
        svc, product, sku, meter = key
        svc = str(svc); product = str(product) if pd.notna(product) else ""
        sku = str(sku) if pd.notna(sku) else ""
        meter = str(meter) if pd.notna(meter) else ""

        # Extended Zones service allowlist (drop anything not in the table).
        if svc not in ALLOWED_SERVICES:
            continue
        # Within Virtual Machines, only keep A/B/D/E/F + NVadsA10v5 series.
        if svc == "Virtual Machines" and not is_allowed_vm(product):
            continue

        rates = {}
        discounts: dict[str, dict[str, float]] = {}

        for label, region_id in REGION_LABEL_TO_ID.items():
            rate_val = rate_pv.at[key, label] if label in rate_pv.columns else None
            if pd.isna(rate_val):
                continue
            rates[region_id] = float(rate_val)

            disc = {}
            for src_pv, disc_key in (
                (sp1y_pv, "sp1y"),
                (sp3y_pv, "sp3y"),
                (ri1y_pv, "ri1y"),
                (ri3y_pv, "ri3y"),
            ):
                if key in src_pv.index and label in src_pv.columns:
                    v = src_pv.at[key, label]
                    if pd.notna(v) and 0 < float(v) < 1:
                        disc[disc_key] = round(float(v), 6)
            if disc:
                discounts[region_id] = disc

        if not rates:
            continue
        entry = {
            "productName": product,
            "skuName": sku,
            "meterType": meter,
            "unitType": unit_type_for_meter(meter),
            "rates": rates,
        }
        if discounts:
            entry["discounts"] = discounts
        services.setdefault(svc, []).append(entry)

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

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataSource": {
            "kind": "uploaded-file",
            "label": "Uploaded file snapshot",
            "generator": "scripts/extract_catalog.py",
        },
        "currency": "USD",
        "regions": REGIONS,
        "services": catalog_services,
    }


def main():
    df = load_all_rows()
    print(f"Loaded {len(df):,} latest rows across regions:")
    print(df["AvailabilityRegion"].value_counts().to_string())
    print(f"  by SalesMotion: {df['SalesMotion'].value_counts().to_dict()}")

    catalog = build_catalog(df)
    total_skus = sum(s["skuCount"] for s in catalog["services"])
    print(f"\nServices: {len(catalog['services'])}, total SKU entries: {total_skus:,}")
    for s in catalog["services"]:
        print(f"  {s['name']}: {s['skuCount']}")

    DATA_DIR.mkdir(exist_ok=True)
    WEB_DIR.mkdir(exist_ok=True)
    out_data = DATA_DIR / "catalog.json"
    out_web = WEB_DIR / "catalog.json"
    out_data.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    out_web.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    print(f"\nWrote {out_data} and {out_web}")


if __name__ == "__main__":
    main()
