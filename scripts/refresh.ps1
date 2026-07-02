# Refresh the Azure Extended Zones pricing catalog and embed it into web/index.html.
#
# Usage (from any directory):
#   pwsh scripts/refresh.ps1
#
# Steps:
#   1. Export "Full AEZ List" xlsx sheet to _tmp_aez.csv via Excel COM
#      (needed because the workbook carries an IRM sensitivity label that
#      openpyxl/xlrd cannot open).
#   2. extract_catalog.py     - reads _tmp_aez.csv and emits data/catalog.json + web/catalog.json
#   3. inline_catalog.py      - inlines web/catalog.json into <script id="inlineCatalog"> in web/index.html
#   4. qa_check.py            - validates invariants; non-zero exit on failure
#
# The public Azure Pricing API fetch step is intentionally disabled while
# the calculator is driven by the uploaded workbook only. Uncomment the
# fetch_pricing_api.py block below to re-enable it.

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    Write-Host "[1/4] Exporting AEZ workbook to CSV via Excel COM..." -ForegroundColor Cyan
    $xlsx = Join-Path $repoRoot "20260626-Full AEZ List June 2026.xlsx"
    $csv  = Join-Path $repoRoot "_tmp_aez.csv"
    if (-not (Test-Path $xlsx)) { throw "Source workbook not found: $xlsx" }
    if (Test-Path $csv) { Remove-Item $csv -Force }

    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    try {
        $wb = $excel.Workbooks.Open($xlsx, 0, $true)
        $sheet = $wb.Sheets.Item(1)
        $sheet.SaveAs($csv, 6)
        $wb.Close($false)
        Write-Host "   Exported $($sheet.Name) -> $csv"
    } finally {
        $excel.Quit()
        [System.Runtime.Interopservices.Marshal]::ReleaseComObject($excel) | Out-Null
    }

    Write-Host "`n[2/4] Extracting catalog from CSV..." -ForegroundColor Cyan
    python scripts/extract_catalog.py
    if ($LASTEXITCODE -ne 0) { throw "extract_catalog.py failed (exit $LASTEXITCODE)" }

    # --- Public Azure Pricing API step (disabled) -------------------------
    # Write-Host "`n[.] Fetching live catalog from Azure pricing API..." -ForegroundColor Cyan
    # python scripts/fetch_pricing_api.py
    # if ($LASTEXITCODE -ne 0) { throw "fetch_pricing_api.py failed (exit $LASTEXITCODE)" }
    # ---------------------------------------------------------------------

    Write-Host "`n[3/4] Inlining catalog into web/index.html..." -ForegroundColor Cyan
    python scripts/inline_catalog.py
    if ($LASTEXITCODE -ne 0) { throw "inline_catalog.py failed (exit $LASTEXITCODE)" }

    Write-Host "`n[4/4] Running QA checks..." -ForegroundColor Cyan
    python scripts/qa_check.py
    if ($LASTEXITCODE -ne 0) { throw "qa_check.py failed (exit $LASTEXITCODE)" }

    Write-Host "`nRefresh complete. Commit web/index.html, web/catalog.json, and data/catalog.json." -ForegroundColor Green
}
finally {
    Pop-Location
}
