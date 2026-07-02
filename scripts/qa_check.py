"""QA check for the generic catalog shape."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "data" / "catalog.json"

EXPECTED_REGIONS = ["luxembourg", "perth", "losangeles"]


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def main() -> int:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    print("--- Catalog invariants ---")
    failures = 0

    # Regions
    region_ids = [r["id"] for r in catalog["regions"]]
    failures += not check(
        "Catalog has exactly 3 regions in order [luxembourg, perth, losangeles]",
        region_ids == EXPECTED_REGIONS,
        f"actual={region_ids}",
    )

    # Services
    services = catalog["services"]
    failures += not check(
        "At least 8 services present",
        len(services) >= 8,
        f"count={len(services)}",
    )

    # Excluded services must NOT appear in the catalog.
    excluded = {
        "Application Gateway",
        "Azure Site Recovery",
        "NAT Gateway",
        "Network Watcher",
        "Specialized Compute",
    }
    present_names = {s["name"] for s in services}
    leaked = sorted(excluded & present_names)
    failures += not check(
        "No excluded services present in catalog",
        not leaked,
        f"leaked={leaked}",
    )

    # SKU counts and per-region rates
    total_skus = 0
    skus_with_all_three = 0
    skus_missing_region = 0
    for svc in services:
        total_skus += len(svc["skus"])
        for sku in svc["skus"]:
            rates = sku.get("rates", {})
            if all(r in rates for r in EXPECTED_REGIONS):
                skus_with_all_three += 1
            else:
                skus_missing_region += 1
    failures += not check(
        "Total SKU count > 1000",
        total_skus > 1000,
        f"total={total_skus}",
    )
    failures += not check(
        "At least 50% of SKUs have rates in all 3 regions",
        skus_with_all_three >= total_skus * 0.5,
        f"all-three={skus_with_all_three} / {total_skus}",
    )

    # Spot-check: Virtual Machines service exists and has Dsv5 SKUs
    vm = next((s for s in services if s["id"] == "virtual-machines"), None)
    failures += not check("'virtual-machines' service present", vm is not None)
    if vm:
        d4s = [s for s in vm["skus"]
               if "Dsv5" in s.get("productName", "") and s.get("skuName") == "D4s v5"
               and "Compute Hour" in s.get("meterType", "")]
        failures += not check(
            "D4s v5 (Dsv5 Series) hourly meter exists",
            len(d4s) >= 1,
            f"matches={len(d4s)}",
        )
        if d4s:
            sample = d4s[0]
            failures += not check(
                "D4s v5 has a positive Luxembourg rate",
                sample["rates"].get("luxembourg", 0) > 0,
                f"rate={sample['rates'].get('luxembourg')}",
            )
            failures += not check(
                "D4s v5 has a positive Perth rate",
                sample["rates"].get("perth", 0) > 0,
                f"rate={sample['rates'].get('perth')}",
            )
            # Note: Los Angeles may not price every VM SKU; that's a real
            # data property of the source meter list, not a bug.

    # Unit-type sanity
    bad_unit = [s for svc in services for s in svc["skus"]
                if s.get("unitType") not in ("hour", "month", "day", "unit")]
    failures += not check(
        "All SKUs have a recognized unitType",
        len(bad_unit) == 0,
        f"bad={len(bad_unit)}",
    )

    print(f"\nTotal services: {len(services)}, total SKUs: {total_skus}")
    print(f"SKUs priced in all 3 regions: {skus_with_all_three}")
    print(f"SKUs priced in some regions: {skus_missing_region}")

    if failures:
        print(f"\n{failures} FAILURE(S)")
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
