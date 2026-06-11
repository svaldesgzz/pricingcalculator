# Refresh the Azure Extended Zones pricing catalog and embed it into web/index.html.
#
# Usage (from any directory):
#   pwsh scripts/refresh.ps1
#
# Steps:
#   1. extract_catalog.py     - reads the .xlsx files and emits data/catalog.json + web/catalog.json
#   2. fetch_pricing_api.py   - fetches public Azure pricing API and emits web/catalog-live.json
#   3. inline_catalog.py      - inlines web/catalog.json into <script id="inlineCatalog"> in web/index.html
#   4. qa_check.py            - validates invariants; non-zero exit on failure

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    Write-Host "[1/4] Extracting catalog from source xlsx files..." -ForegroundColor Cyan
    python scripts/extract_catalog.py
    if ($LASTEXITCODE -ne 0) { throw "extract_catalog.py failed (exit $LASTEXITCODE)" }

    Write-Host "`n[2/4] Fetching live catalog from Azure pricing API..." -ForegroundColor Cyan
    python scripts/fetch_pricing_api.py
    if ($LASTEXITCODE -ne 0) { throw "fetch_pricing_api.py failed (exit $LASTEXITCODE)" }

    Write-Host "`n[3/4] Inlining catalog into web/index.html..." -ForegroundColor Cyan
    python scripts/inline_catalog.py
    if ($LASTEXITCODE -ne 0) { throw "inline_catalog.py failed (exit $LASTEXITCODE)" }

    Write-Host "`n[4/4] Running QA checks..." -ForegroundColor Cyan
    python scripts/qa_check.py
    if ($LASTEXITCODE -ne 0) { throw "qa_check.py failed (exit $LASTEXITCODE)" }

    if (-not (Test-Path "web/catalog-live.json")) {
        throw "web/catalog-live.json missing after refresh"
    }

    Write-Host "`nRefresh complete. Commit web/index.html, web/catalog.json, web/catalog-live.json, and data/catalog.json." -ForegroundColor Green
}
finally {
    Pop-Location
}
