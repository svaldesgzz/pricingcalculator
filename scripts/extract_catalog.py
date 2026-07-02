"""
Build catalog.json by reading the "Full AEZ List" workbook and merging it into
a single generic catalog the calculator can render.

The current source is the DRM-protected workbook:
    20260626-Full AEZ List June 2026.xlsx

Because the workbook has an Information-Protection sensitivity label, plain
openpyxl / xlrd cannot open it. `scripts/refresh.ps1` handles that up-front by
using Excel COM to export the sheet to `_tmp_aez.csv`. This script prefers the
CSV when present and only falls back to the raw xlsx (unprotected files).

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

AEZ_XLSX = ROOT / "20260626-Full AEZ List June 2026.xlsx"
AEZ_CSV = ROOT / "_tmp_aez.csv"  # produced by refresh.ps1 via Excel COM

# --- Legacy sources (kept for reference; no longer read) ---
# LUX_XLSX = ROOT / "20260513 - Luxembourg SKU Pricing May 2026.xlsx"
# PERTH_LA_XLSX = ROOT / "20260519 - Perth + LA - Meter List (May19).xlsx"

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
# table are included, minus the additional exclusion list below.
ALLOWED_SERVICES = {
    "Virtual Machines",
    "Azure Kubernetes Service",
    "Storage",
    "Backup",
    "ExpressRoute",
    "Virtual Network",
    "Load Balancer",
    "Azure Firewall",
    "Azure DDOS Protection",
}

# Services intentionally excluded from the calculator until they land in
# the Extended Zones offering. Update this list as availability changes.
EXCLUDED_SERVICES = {
    "Application Gateway",
    "Azure Site Recovery",
    "NAT Gateway",
    "Network Watcher",
    "Specialized Compute",
}


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
    if low.startswith(("internal", "gen", "cloud")):
        return False
    first = token[0].upper()
    return first in {"A", "B", "D", "E", "F"}


def _read_xlsx(path: Path) -> pd.DataFrame:
    """Copy first to bypass file locks (Excel may keep the file open)."""
    tmp = ROOT / f"_tmp_{path.stem}.xlsx"
    shutil.copyfile(path, tmp)
    try:
        df = pd.read_excel(tmp, engine="openpyxl")
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
    return df


def load_all_rows() -> pd.DataFrame:
    """Load all latest rows for our 3 regions.

    Prefers the pre-exported `_tmp_aez.csv` (produced by refresh.ps1 to work
    around the workbook's IRM sensitivity label). Falls back to reading the
    xlsx directly if the CSV is missing (works only for unprotected files).
    """
    if AEZ_CSV.exists():
        print(f"Reading {AEZ_CSV.name} (CSV export)", file=sys.stderr)
        df = pd.read_csv(AEZ_CSV, low_memory=False)
    elif AEZ_XLSX.exists():
        print(f"Reading {AEZ_XLSX.name} directly", file=sys.stderr)
        df = _read_xlsx(AEZ_XLSX)
    else:
        raise RuntimeError(
            f"Neither {AEZ_CSV.name} nor {AEZ_XLSX.name} was found. "
            "Run scripts/refresh.ps1 or export the xlsx to CSV manually."
        )
    # Excel COM writes CSVs with the user's locale (thousand separators, etc.).
    # Coerce numeric columns back to floats.
    for col in ("CurrentRate", "SavingsPlanOneYearDiscount",
                "SavingsPlanThreeYearsDiscount", "RIDiscount", "SpotDiscount"):
        if col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].astype(str).str.replace(",", "", regex=False)
            df[col] = pd.to_numeric(df[col], errors="coerce")
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
    payg = df[(df["SalesMotion"] == "OnDemand") & (df["RateType"] == "Standard")]
    payg = payg.dropna(subset=["CurrentRate"])
    ri = df[df["SalesMotion"] == "ReservedInstance"].copy()
    ri = ri.dropna(subset=["RIDiscount"])

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

    ri_grouped = (
        ri.groupby(
            ["ServiceName", "ProductName", "SkuName", "MeterType",
             "AvailabilityRegion", "ReservationDuration"],
            dropna=False,
        )["RIDiscount"]
        .max()
        .reset_index()
    )

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
    ri1y_pv = _pivot(ri_grouped[ri_grouped["ReservationDuration"] == "1 Year"], "RIDiscount")
    ri3y_pv = _pivot(ri_grouped[ri_grouped["ReservationDuration"] == "3 Years"], "RIDiscount")

    services: dict[str, list[dict]] = {}
    for key in rate_pv.index:
        svc, product, sku, meter = key
        svc = str(svc); product = str(product) if pd.notna(product) else ""
        sku = str(sku) if pd.notna(sku) else ""
        meter = str(meter) if pd.notna(meter) else ""

        if svc in EXCLUDED_SERVICES:
            continue
        if svc not in ALLOWED_SERVICES:
            continue
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
            "label": "Full AEZ List (uploaded file snapshot)",
            "generator": "scripts/extract_catalog.py",
            "sourceFile": AEZ_XLSX.name,
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
    print(f"  excluded services: {sorted(EXCLUDED_SERVICES)}")

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
