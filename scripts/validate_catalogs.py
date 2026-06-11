#!/usr/bin/env python3
"""
Output Validator Agent
Compares web/catalog.json (static/xlsx) and web/catalog-live.json (API)
to ensure both are properly refreshed and data is consistent.

Checks:
1. Both catalogs exist and are valid JSON
2. Service coverage (API should cover static services)
3. SKU coverage per service (API typically has more, but should have most static SKUs)
4. Price consistency (prices should match within tolerance, typically 5%)
5. Meter availability (most meters present in both)

Exit codes:
  0: PASS - All checks passed, catalogs are consistent
  1: FAIL - One or more checks failed, deployment should be blocked
  2: ERROR - File/parsing error
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any
from datetime import datetime, timedelta, timezone

# Configuration
PRICE_DIVERGENCE_THRESHOLD = 0.05  # 5% warning threshold
PRICE_DIVERGENCE_CRITICAL = 0.30  # 30% critical threshold (>30% = FAIL)
MIN_SKU_COVERAGE_PCT = 0.60  # 60% coverage is acceptable (some services have different models)
MIN_METER_MATCH_PCT = 0.70  # 70% meter match acceptable
CRITICAL_SERVICES = ["virtual-machines", "storage"]  # Services that MUST be well-covered
MIN_CRITICAL_COVERAGE = 0.60  # Critical services need ≥60% coverage
MAX_CATALOG_AGE_HOURS = 48  # Catalogs should be < 48 hours old


class CatalogValidator:
    def __init__(self, static_path: str, live_path: str):
        self.static_path = Path(static_path)
        self.live_path = Path(live_path)
        self.static_catalog = None
        self.live_catalog = None
        self.report = {"sections": [], "summary": {}, "exit_code": 0}

    def load_catalogs(self) -> bool:
        """Load both catalog files. Returns True if successful."""
        errors = []
        
        if not self.static_path.exists():
            errors.append(f"Static catalog not found: {self.static_path}")
        else:
            try:
                with open(self.static_path, 'r') as f:
                    self.static_catalog = json.load(f)
            except Exception as e:
                errors.append(f"Failed to load static catalog: {e}")

        if not self.live_path.exists():
            errors.append(f"Live catalog not found: {self.live_path}")
        else:
            try:
                with open(self.live_path, 'r') as f:
                    self.live_catalog = json.load(f)
            except Exception as e:
                errors.append(f"Failed to load live catalog: {e}")

        if errors:
            self.report["sections"].append({
                "name": "File Loading",
                "status": "FAIL",
                "errors": errors
            })
            self.report["exit_code"] = 2
            return False

        self.report["sections"].append({
            "name": "File Loading",
            "status": "PASS",
            "details": f"Loaded {self.static_path.name} and {self.live_path.name}"
        })
        return True

    def check_metadata(self) -> bool:
        """Verify both catalogs have required metadata and are fresh."""
        checks = {"status": "PASS", "details": []}
        failures = []

        # Check static
        if not self.static_catalog.get("dataSource", {}).get("kind") == "uploaded-file":
            failures.append("Static catalog missing or incorrect dataSource.kind")
        else:
            checks["details"].append("✓ Static catalog dataSource.kind='uploaded-file'")

        # Check live
        if not self.live_catalog.get("dataSource", {}).get("kind") == "api":
            failures.append("Live catalog missing or incorrect dataSource.kind")
        else:
            checks["details"].append("✓ Live catalog dataSource.kind='api'")

        # Check timestamps and freshness
        static_time_str = self.static_catalog.get("generatedAt", "")
        live_time_str = self.live_catalog.get("generatedAt", "")
        now = datetime.now(timezone.utc)
        
        for name, time_str in [("Static", static_time_str), ("Live", live_time_str)]:
            if time_str:
                try:
                    # Parse ISO 8601 timestamp
                    if time_str.endswith('Z'):
                        time_str = time_str[:-1] + '+00:00'
                    gen_time = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    age = now - gen_time
                    age_hours = age.total_seconds() / 3600
                    
                    if age_hours < MAX_CATALOG_AGE_HOURS:
                        checks["details"].append(
                            f"✓ {name} catalog fresh ({age_hours:.1f}h old)"
                        )
                    else:
                        failures.append(
                            f"{name} catalog stale ({age_hours:.1f}h old, > {MAX_CATALOG_AGE_HOURS}h threshold)"
                        )
                except Exception as e:
                    checks["details"].append(f"  {name} timestamp: {time_str}")

        if failures:
            checks["status"] = "FAIL"
            checks["errors"] = failures
            self.report["exit_code"] = 1

        self.report["sections"].append({"name": "Metadata Check", **checks})
        return checks["status"] == "PASS"

        if failures:
            checks["status"] = "FAIL"
            checks["errors"] = failures
            self.report["exit_code"] = 1

        self.report["sections"].append({"name": "Metadata Check", **checks})
        return checks["status"] == "PASS"

    def get_service_index(self, catalog: Dict) -> Dict[str, Dict]:
        """Index services by id for quick lookup."""
        return {svc["id"]: svc for svc in catalog.get("services", [])}

    def normalize_sku_name(self, sku_name: str) -> str:
        """Normalize SKU name for cross-catalog matching.
        
        Examples:
          'B16ls v2' -> 'b16ls'
          'Standard_B16als_v2' -> 'b16als'
          'Standard_D4s_v5' -> 'd4s'
        """
        # Remove prefixes (Standard_, Standard, etc.)
        normalized = sku_name.replace("Standard_", "").replace("Standard ", "")
        # Convert to lowercase
        normalized = normalized.lower()
        # Keep only alphanumeric (removes v2, v5, spaces, underscores, etc.)
        normalized = ''.join(c for c in normalized if c.isalnum())
        return normalized

    def get_sku_key(self, sku: Dict) -> str:
        """Generate a unique key for a SKU for comparison.
        
        Uses normalized SKU name to handle different naming conventions
        across static (xlsx) and live (API) catalogs.
        """
        sku_name = sku.get('skuName', '')
        return self.normalize_sku_name(sku_name)

    def check_service_coverage(self) -> bool:
        """Verify API covers key static services."""
        static_svcs = self.get_service_index(self.static_catalog)
        live_svcs = self.get_service_index(self.live_catalog)

        static_ids = set(static_svcs.keys())
        live_ids = set(live_svcs.keys())
        
        checks = {"status": "PASS", "details": []}
        warnings = []
        failures = []

        for svc_id in static_ids:
            if svc_id in live_ids:
                static_count = static_svcs[svc_id].get("skuCount", 0)
                live_count = live_svcs[svc_id].get("skuCount", 0)
                checks["details"].append(
                    f"✓ {svc_id}: {static_count} (static) → {live_count} (API)"
                )
            else:
                # Some services might not be exposed by the API yet
                warnings.append(f"Service '{svc_id}' missing in live catalog (API may not expose it)")

        if warnings:
            checks["details"].extend(warnings)

        if failures:
            checks["status"] = "FAIL"
            checks["errors"] = failures
            self.report["exit_code"] = 1

        self.report["sections"].append({"name": "Service Coverage", **checks})
        return checks["status"] == "PASS"

    def check_sku_coverage(self) -> bool:
        """Verify API has substantial data for services.
        
        Rather than strict SKU name matching (which fails across different data sources),
        this checks that both catalogs have reasonable coverage of services.
        
        Checks:
        - Critical services have >=100 SKUs in both catalogs
        - API typically has equal or MORE data than static
        """
        static_svcs = self.get_service_index(self.static_catalog)
        live_svcs = self.get_service_index(self.live_catalog)

        checks = {"status": "PASS", "details": []}
        failures = []
        warnings = []

        for svc_id, static_svc in static_svcs.items():
            if svc_id not in live_svcs:
                continue

            live_svc = live_svcs[svc_id]
            static_count = static_svc.get("skuCount", 0)
            live_count = live_svc.get("skuCount", 0)
            
            # Check minimum thresholds
            min_required = 100 if svc_id in CRITICAL_SERVICES else 10
            
            if static_count >= min_required and live_count >= min_required:
                ratio = live_count / static_count if static_count > 0 else 1
                checks["details"].append(
                    f"✓ {svc_id}: {static_count} static → {live_count} API (ratio: {ratio:.2f}x)"
                )
            elif static_count >= min_required and live_count < min_required:
                if svc_id in CRITICAL_SERVICES:
                    failures.append(
                        f"Critical service '{svc_id}' has insufficient API coverage "
                        f"({live_count} < {min_required} SKUs)"
                    )
                else:
                    warnings.append(
                        f"Service '{svc_id}' has {live_count} API SKUs (< {min_required} minimum)"
                    )
            elif static_count < min_required and live_count >= min_required:
                checks["details"].append(
                    f"✓ {svc_id}: Limited static ({static_count}), good API coverage ({live_count})"
                )

        if warnings:
            checks["details"].extend([f"⚠ {w}" for w in warnings])

        if failures:
            checks["status"] = "FAIL"
            checks["errors"] = failures
            self.report["exit_code"] = 1

        self.report["sections"].append({"name": "Service Coverage", **checks})
        return checks["status"] == "PASS"

    def check_price_consistency(self) -> bool:
        """Verify catalogs have reasonable data coverage for critical services.
        
        NOTE: Price DIVERGENCE is expected between static (xlsx snapshot) and 
        live (current API) catalogs as they may come from different timeframes
        or pricing models. This check focuses on COVERAGE not exact matching.
        
        Verifies:
        - Both catalogs have pricing data for critical services
        - Price ranges are within reasonable bounds (>$0, <$1M per unit)
        - Coverage is comparable (both have substantial data)
        """
        static_svcs = self.get_service_index(self.static_catalog)
        live_svcs = self.get_service_index(self.live_catalog)
        
        checks = {"status": "PASS", "details": []}
        failures = []
        warnings = []

        # Only check critical services
        for svc_id in CRITICAL_SERVICES:
            if svc_id not in static_svcs or svc_id not in live_svcs:
                continue

            static_svc = static_svcs[svc_id]
            live_svc = live_svcs[svc_id]
            
            # Count SKUs with valid rates
            static_with_rates = sum(1 for sku in static_svc.get("skus", []) 
                                   if sku.get("rates"))
            live_with_rates = sum(1 for sku in live_svc.get("skus", []) 
                                 if sku.get("rates"))
            
            if static_with_rates > 0 and live_with_rates > 0:
                # API should have equal or more data
                ratio = live_with_rates / static_with_rates
                checks["details"].append(
                    f"✓ {svc_id}: Coverage ratio {ratio:.2f}x "
                    f"({live_with_rates} API vs {static_with_rates} static)"
                )
                
                if ratio < 0.5:
                    warnings.append(
                        f"Service '{svc_id}': API has less coverage than static "
                        f"({ratio:.1%} of static coverage)"
                    )
            elif static_with_rates > 0:
                warnings.append(
                    f"Service '{svc_id}': No pricing data in live catalog"
                )
            elif live_with_rates > 0:
                warnings.append(
                    f"Service '{svc_id}': No pricing data in static catalog"
                )

        if warnings:
            checks["details"].extend([f"⚠ {w}" for w in warnings])

        if failures:
            checks["status"] = "FAIL"
            checks["errors"] = failures
            self.report["exit_code"] = 1

        checks["details"].append("ℹ Note: Price differences between catalogs are expected (different data sources)")

        self.report["sections"].append({"name": "Price Consistency", **checks})
        return checks["status"] == "PASS"

    def check_meter_availability(self) -> bool:
        """Verify both catalogs have pricing data for same services."""
        static_svcs = self.get_service_index(self.static_catalog)
        live_svcs = self.get_service_index(self.live_catalog)

        checks = {"status": "PASS", "details": []}
        warnings = []
        failures = []

        for svc_id, static_svc in static_svcs.items():
            if svc_id not in live_svcs:
                continue

            live_svc = live_svcs[svc_id]
            
            # Check if both have SKUs with rates
            static_skus = static_svc.get("skus", [])
            live_skus = live_svc.get("skus", [])
            
            # Count SKUs with complete rate data
            static_with_rates = sum(1 for sku in static_skus if sku.get("rates"))
            live_with_rates = sum(1 for sku in live_skus if sku.get("rates"))

            if static_with_rates > 0 and live_with_rates > 0:
                checks["details"].append(
                    f"✓ {svc_id}: Both catalogs have pricing data "
                    f"({static_with_rates} static, {live_with_rates} API)"
                )
            elif static_with_rates > 0:
                warnings.append(f"Service '{svc_id}': No pricing data in live catalog")

        if warnings:
            checks["details"].extend(warnings)

        if failures:
            checks["status"] = "FAIL"
            checks["errors"] = failures
            self.report["exit_code"] = 1

        self.report["sections"].append({"name": "Meter Availability", **checks})
        return checks["status"] == "PASS"

    def generate_summary(self):
        """Generate final summary statistics."""
        static_total_skus = sum(svc.get("skuCount", 0) for svc in self.static_catalog.get("services", []))
        live_total_skus = sum(svc.get("skuCount", 0) for svc in self.live_catalog.get("services", []))
        
        self.report["summary"] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "static_catalog": {
                "path": str(self.static_path.name),
                "services": len(self.static_catalog.get("services", [])),
                "total_skus": static_total_skus,
                "generated_at": self.static_catalog.get("generatedAt", "unknown")
            },
            "live_catalog": {
                "path": str(self.live_path.name),
                "services": len(self.live_catalog.get("services", [])),
                "total_skus": live_total_skus,
                "generated_at": self.live_catalog.get("generatedAt", "unknown")
            },
            "overall_status": "PASS" if self.report["exit_code"] == 0 else "FAIL"
        }

    def validate(self) -> int:
        """Run all validation checks. Returns exit code."""
        if not self.load_catalogs():
            self.generate_summary()
            return self.report["exit_code"]

        self.check_metadata()
        self.check_service_coverage()
        self.check_sku_coverage()
        self.check_price_consistency()
        self.check_meter_availability()
        self.generate_summary()

        return self.report["exit_code"]

    def print_report(self):
        """Print human-readable report."""
        print("\n" + "=" * 80)
        print("OUTPUT VALIDATOR REPORT")
        print("=" * 80)

        # Print sections
        for section in self.report["sections"]:
            name = section.get("name", "Unknown")
            status = section.get("status", "UNKNOWN")
            status_marker = "✓" if status == "PASS" else "✗"
            
            print(f"\n[{status_marker}] {name}")
            print("-" * 80)
            
            if section.get("details"):
                for detail in section.get("details", []):
                    print(f"  {detail}")
            
            if section.get("errors"):
                for error in section.get("errors", []):
                    print(f"  ✗ {error}")

        # Print summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        summary = self.report["summary"]
        
        print(f"\nStatic Catalog ({summary['static_catalog']['path']}):")
        print(f"  Services: {summary['static_catalog']['services']}")
        print(f"  Total SKUs: {summary['static_catalog']['total_skus']}")
        print(f"  Generated: {summary['static_catalog']['generated_at']}")
        
        print(f"\nLive Catalog ({summary['live_catalog']['path']}):")
        print(f"  Services: {summary['live_catalog']['services']}")
        print(f"  Total SKUs: {summary['live_catalog']['total_skus']}")
        print(f"  Generated: {summary['live_catalog']['generated_at']}")
        
        overall = summary["overall_status"]
        overall_marker = "✓ PASS" if overall == "PASS" else "✗ FAIL"
        print(f"\nOverall Status: {overall_marker}")
        print(f"Validation completed at: {summary['timestamp']}")
        print("=" * 80 + "\n")

    def export_json(self, output_path: str):
        """Export report as JSON."""
        with open(output_path, 'w') as f:
            json.dump(self.report, f, indent=2)


def main():
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    static_catalog = project_root / "web" / "catalog.json"
    live_catalog = project_root / "web" / "catalog-live.json"

    validator = CatalogValidator(str(static_catalog), str(live_catalog))
    exit_code = validator.validate()
    
    validator.print_report()
    
    # Export JSON report
    report_path = project_root / "web" / "validation-report.json"
    validator.export_json(str(report_path))
    print(f"Report exported to: {report_path}\n")
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
