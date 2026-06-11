# Live Azure Pricing API Integration

## Overview

The pricing calculator now supports loading live pricing data from the **public Azure Pricing API** (`https://prices.azure.com/api/retail/prices`) instead of relying solely on static Excel files.

### Key Features

- **Public & Unauthenticated**: No credentials required; works directly from the browser
- **CORS-Enabled**: Can be called from browser JavaScript
- **Real-Time Data**: Automatic pagination to fetch all pricing SKUs
- **Fallback Support**: Static `catalog.json` used if API is unavailable
- **Local Caching**: 24-hour cache in `localStorage` to avoid repeated API calls
- **Learn Page Compatible**: Works on a standalone HTML page (no backend required)

---

## Implementation

### 1. Browser-Side Integration (`web/index.html`)

Two new functions added:

#### `loadCatalog()`
Updated to check `localStorage` cache before falling back to static files:
```javascript
async function loadCatalog() {
  // Try localStorage cache first (from live API fetch)
  const cached = localStorage.getItem("pricingcalc_catalog_live");
  if (cached) { return JSON.parse(cached); }
  
  // Fall back to static catalog.json or inlined catalog
  ...
}
```

#### `fetchLivePricingCatalog()`
Queries the Azure Pricing API and caches results:
```javascript
async function fetchLivePricingCatalog() {
  // Check 24-hour cache validity
  // Fetch from https://prices.azure.com/api/retail/prices?$filter=...
  // Cache result in localStorage
  // Update UI status
}
```

#### UI Button
"Load live data" button added to the top notice area. When clicked:
1. Disables the button and shows "Fetching live pricing..."
2. Calls `fetchLivePricingCatalog()`
3. On success: reloads catalog, clears cart, re-renders UI, shows "✓ Live data loaded (cached 24h)"
4. On failure: displays error message and retains static data

---

### 2. Python Extraction Script (`scripts/fetch_pricing_api.py`)

Standalone script to fetch and transform API data:

```bash
python scripts/fetch_pricing_api.py
```

**Output**: `web/catalog-live.json` (same schema as static `catalog.json`)

**Features**:
- Queries each Extended Zones service separately
- Handles API pagination automatically
- Filters to Extended Zones regions: Luxembourg (`luxbg`), Perth (`au east`), Los Angeles (`us west`)
- Applies VM series allowlist (A/B/D/E/F + NVadsA10v5 only)
- Matches static extraction logic (same filters & allowlists)

**Usage**:
```bash
# Fetch once and cache result
python scripts/fetch_pricing_api.py

# Then on the HTML page, click "Load live data" to use it
```

---

## Data Flow

```
┌─────────────────────────┐
│   HTML Page Loads       │
└────────────┬────────────┘
             │
             ├─→ Check localStorage cache
             │   └─→ If valid: use cached catalog
             │
             ├─→ Otherwise: load static catalog.json
             │   └─→ Or: inlined catalog in HTML
             │
             └─→ Display UI with pricing mode options
                 │
                 └─→ User clicks "Load live data"
                     │
                     ├─→ Fetch from Azure Pricing API
                     ├─→ Cache in localStorage (24h)
                     ├─→ Clear cart
                     ├─→ Reload UI with live data
                     └─→ Show success message
```

---

## API Query Examples

### Simple Service Query
```javascript
const filter = "serviceName eq 'Virtual Machines' and priceType eq 'Consumption'";
const url = `https://prices.azure.com/api/retail/prices?$filter=${encodeURIComponent(filter)}`;
const response = await fetch(url);
const data = await response.json();
```

### Extended Zones Only
```javascript
const regions = ["luxbg", "au east", "us west"];
const filter = `(location eq '${regions.join("' or location eq '")}') and priceType eq 'Consumption'`;
```

### Pagination
The API returns:
```json
{
  "Items": [ /* up to 100 results */ ],
  "NextPageLink": "https://prices.azure.com/...?$skip=100&..."
}
```

---

## Limitations & Future Work

### Current Limitations
1. **VM Volume**: API returns all global VMs (~6,700 SKUs), not just Extended Zones. Static script is more selective (~1,626).
2. **Savings Plan Data**: API's current data structure may not include discount factors. Would need additional processing.
3. **Rate Selection**: API returns all rate types (consumption, reservation, DevTest). Script only uses `Consumption` and filters manually.

### Future Enhancements
1. **Real-Time Discount Mapping**: Fetch savings plan discount data from a separate API endpoint or dataset
2. **Dedicated Backend**: Create a lightweight Node.js/Python backend to:
   - Pre-filter to Extended Zones SKUs only
   - Cache transformed catalogs (avoid browser-side processing)
   - Serve optimized JSON to the HTML page
3. **Comparison Mode**: Show "old price" vs "new price" when live data differs from static
4. **Export Integration**: Include last-fetch timestamp in CSV exports

---

## Testing

### Manual Test (Browser)
1. Open `web/index.html` in a browser
2. Observe it loads with static catalog data
3. Click "Load live data" button
4. Wait 30-60 seconds (API pagination takes time)
5. See catalog refresh with live data
6. Refresh the page: data persists from localStorage cache

### Programmatic Test (Python)
```bash
python scripts/fetch_pricing_api.py
# Check exit code: 0 = success, 1 = fetch failed
# Output: web/catalog-live.json
```

---

## Architecture Notes

### Why Public Endpoint?
The Azure Pricing API at `prices.azure.com/api/retail/prices` is deliberately public and unauthenticated. This aligns with Microsoft's goal to make pricing transparent and queryable. No credentials needed.

### Why Browser-Side Fetching?
For a "learn page" context (standalone HTML), there's no backend. Browser-side fetching + localStorage caching provides:
- No server deployment needed
- Fast subsequent loads
- Resilient fallback to static data
- User control ("Load live data" button)

### Why Python Script Too?
The Python script enables:
- Batch processing without browser overhead
- Version control of extracted data (commit to repo)
- Integration with CI/CD pipelines
- More complex transformations than feasible in-browser

---

## Troubleshooting

### "Failed to fetch live pricing: Network error"
- Check browser console for CORS or timeout errors
- Verify `prices.azure.com` is reachable from your network
- Try again after a few seconds (API may be rate-limited)

### "No Extended Zones pricing found"
- The API may not have data for the specific regions in that time period
- Check the filter string in the browser console
- Ensure `lu`, `au east`, or `us west` are in the `location` field

### "Load live data" button does nothing
- Check browser console for JavaScript errors
- Verify `fetchLivePricingCatalog()` function exists
- Ensure `web/index.html` has the updated code

---

## References

- **Azure Pricing API Docs**: [Learn - Price Partner SDK](https://learn.microsoft.com/en-us/azure/cost-management-billing/cost-management-automation/price-partner-sdk/)
- **API Endpoint**: `https://prices.azure.com/api/retail/prices`
- **OData Filter Syntax**: [OData Version 4.0](https://docs.oasis-open.org/odata/odata/v4.0/os/complete/part2-url-conventions/odata-v4.0-os-part2-url-conventions.html#_Toc372793845)

---

## Credits

Integration inspired by Adithya Sridhar's suggestion to leverage the public Azure Pricing API for live data instead of static Excel snapshots.
