"""
Hypothesis testing for Extended Zone API exposure.

H2: Inspect Perth vs westus records side-by-side for any discriminator field
    that could be the missing filter for Lux/LA.

H3: Try multiple api-version parameter values to see if any expose more data.
"""

from __future__ import annotations

import json
import sys
import time
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import HTTPError

ENDPOINT = "https://prices.azure.com/api/retail/prices"


def fetch(filter_expr=None, api_version=None, extra_params=None, retries=3):
    params = {}
    if filter_expr:
        params["$filter"] = filter_expr
    if api_version:
        params["api-version"] = api_version
    if extra_params:
        params.update(extra_params)
    url = ENDPOINT + ("?" + urlencode(params) if params else "")
    for attempt in range(retries):
        try:
            with urlopen(url, timeout=30) as resp:
                data = json.loads(resp.read())
                items = data.get("Items", [])
                return {
                    "ok": True,
                    "url": url,
                    "count": len(items),
                    "has_next": bool(data.get("NextPageLink")),
                    "items": items,
                    "raw_top_keys": list(data.keys()),
                }
        except HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                wait = 8 * (attempt + 1)
                print(f"  Rate limited, waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            return {"ok": False, "error": f"HTTP {e.code}", "url": url}
        except Exception as e:
            return {"ok": False, "error": str(e), "url": url}
    return {"ok": False, "error": "exhausted retries"}


def find_field_differences(perth_items, westus_items):
    """Compare Perth and westus records to find distinguishing fields."""
    if not perth_items or not westus_items:
        return {}

    perth_keys = set()
    for item in perth_items:
        perth_keys.update(item.keys())
    westus_keys = set()
    for item in westus_items:
        westus_keys.update(item.keys())

    perth_only_keys = perth_keys - westus_keys
    westus_only_keys = westus_keys - perth_keys
    shared_keys = perth_keys & westus_keys

    perth_values = {k: set() for k in shared_keys}
    westus_values = {k: set() for k in shared_keys}
    for item in perth_items:
        for k in shared_keys:
            v = item.get(k)
            if isinstance(v, (str, int, float, bool)) or v is None:
                perth_values[k].add(v)
    for item in westus_items[:200]:
        for k in shared_keys:
            v = item.get(k)
            if isinstance(v, (str, int, float, bool)) or v is None:
                westus_values[k].add(v)

    distinguishing = {}
    for k in shared_keys:
        pv = perth_values[k]
        wv = westus_values[k]
        # Field is distinguishing if Perth has values not in westus, or vice-versa
        if pv and wv and pv.isdisjoint(wv):
            distinguishing[k] = {
                "perth_unique_values": sorted(str(v) for v in list(pv)[:10]),
                "westus_unique_values": sorted(str(v) for v in list(wv)[:10]),
            }

    return {
        "perth_only_keys": sorted(perth_only_keys),
        "westus_only_keys": sorted(westus_only_keys),
        "fully_distinguishing_fields": distinguishing,
    }


def h2_inspect_records():
    print("\n" + "=" * 70)
    print("H2: Inspect Perth records vs westus records")
    print("=" * 70)

    print("\nFetching Perth (all 74 items)...")
    perth = fetch("armRegionName eq 'perth'")
    print(f"  Got {perth.get('count')} items")

    time.sleep(3)

    # Pull a comparable westus VM/Storage subset (one page is enough for field comparison)
    print("\nFetching westus VM/Storage sample (one page)...")
    westus = fetch(
        "armRegionName eq 'westus' and (serviceName eq 'Virtual Machines' or serviceName eq 'Storage')"
    )
    print(f"  Got {westus.get('count')} items")

    if not perth.get("ok") or not westus.get("ok"):
        print("Cannot compare - one query failed")
        return None

    # Compare a single Perth record with a westus record of similar service
    print("\n--- One Perth record (full):")
    if perth["items"]:
        print(json.dumps(perth["items"][0], indent=2))

    print("\n--- One westus record (full):")
    if westus["items"]:
        print(json.dumps(westus["items"][0], indent=2))

    diff = find_field_differences(perth["items"], westus["items"])
    print("\n=== Field analysis ===")
    print(f"Keys only in Perth records: {diff.get('perth_only_keys')}")
    print(f"Keys only in westus records: {diff.get('westus_only_keys')}")
    print("\nFully distinguishing fields (no value overlap):")
    print(json.dumps(diff.get("fully_distinguishing_fields", {}), indent=2))

    return {
        "perth_count": perth.get("count"),
        "westus_count": westus.get("count"),
        "field_diff": diff,
        "perth_first": perth["items"][0] if perth["items"] else None,
        "westus_first": westus["items"][0] if westus["items"] else None,
    }


def h3_test_api_versions():
    print("\n" + "=" * 70)
    print("H3: Test different api-version values")
    print("=" * 70)

    versions_to_try = [
        None,  # default
        "2021-10-01-preview",
        "2023-01-01-preview",
        "2023-12-01",
        "2024-01-01",
        "2024-08-01",
        "2025-01-01",
        "2026-01-01",
    ]

    results = {}
    for v in versions_to_try:
        label = v or "default"
        print(f"\nTrying api-version={label} with armRegionName eq 'losangeles'")
        r = fetch("armRegionName eq 'losangeles'", api_version=v)
        print(f"  -> ok={r.get('ok')} count={r.get('count')}")
        results[label] = {"count": r.get("count"), "url": r.get("url"), "error": r.get("error")}
        time.sleep(2)

    # Also try an api-version with the broad "list everything for service+region"
    # to see if any version returns extra fields/regions
    print("\n--- Trying preview api-versions for any field discovery ---")
    for v in ["2023-01-01-preview", "2024-01-01-preview"]:
        r = fetch("serviceName eq 'Virtual Machines'", api_version=v)
        if r.get("ok") and r.get("items"):
            keys = sorted({k for item in r["items"][:50] for k in item.keys()})
            print(f"\napi-version={v} top-level item keys: {keys}")
        time.sleep(2)

    return results


if __name__ == "__main__":
    h2 = h2_inspect_records()
    h3 = h3_test_api_versions()

    out = {
        "h2_record_inspection": h2,
        "h3_api_version_tests": h3,
    }
    with open("web/hypothesis_findings.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nSaved findings to web/hypothesis_findings.json")
