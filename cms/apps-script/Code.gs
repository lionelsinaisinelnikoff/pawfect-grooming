/**
 * Pawfect Grooming — Google Sheets CMS
 * Google Apps Script Web App that exposes your sheets as a clean JSON API.
 *
 * Deploy this as a Web App (Execute as: Me, Access: Anyone).
 * 
 * Sheets expected:
 *   - Settings (key/value)
 *   - Services
 *   - Groomers
 *   - Gallery
 *   - Testimonials
 */

const CACHE_TTL_SECONDS = 300; // 5 minutes — change to 0 to disable during development

/**
 * Main entry point for GET requests.
 * Examples:
 *   ?all=true
 *   ?sheet=Services
 *   ?sheet=Gallery&type=dog
 *   ?sheet=Groomers&active=true
 */
function doGet(e) {
  const params = e.parameter || {};
  const cache = CacheService.getScriptCache();

  try {
    // Get the active spreadsheet
    const ss = SpreadsheetApp.getActiveSpreadsheet();

    // Single sheet request
    if (params.sheet) {
      const sheetName = params.sheet;
      const cacheKey = `sheet_${sheetName}_${JSON.stringify(params)}`;

      let result = cache.get(cacheKey);
      if (result && CACHE_TTL_SECONDS > 0) {
        return jsonResponse(JSON.parse(result));
      }

      const data = getSheetAsArray(ss, sheetName, params);
      const payload = { success: true, sheet: sheetName, count: data.length, data };

      if (CACHE_TTL_SECONDS > 0) cache.put(cacheKey, JSON.stringify(payload), CACHE_TTL_SECONDS);
      return jsonResponse(payload);
    }

    // Return everything in one call
    if (params.all === 'true' || params.all === '1') {
      const cacheKey = 'all_content';

      let result = cache.get(cacheKey);
      if (result && CACHE_TTL_SECONDS > 0) {
        return jsonResponse(JSON.parse(result));
      }

      const payload = {
        success: true,
        timestamp: new Date().toISOString(),
        Settings: getSettingsAsObject(ss),
        Services: getSheetAsArray(ss, 'Services', params),
        Groomers: getSheetAsArray(ss, 'Groomers', params),
        Gallery: getSheetAsArray(ss, 'Gallery', params),
        Testimonials: getSheetAsArray(ss, 'Testimonials', params)
      };

      if (CACHE_TTL_SECONDS > 0) cache.put(cacheKey, JSON.stringify(payload), CACHE_TTL_SECONDS);
      return jsonResponse(payload);
    }

    // Default: helpful info
    return jsonResponse({
      success: true,
      message: "Pawfect Grooming CMS API",
      usage: [
        "?all=true                      → Full site content",
        "?sheet=Services                → All services",
        "?sheet=Groomers&active=true    → Only active groomers",
        "?sheet=Gallery&type=dog        → Only dog photos",
        "?sheet=Testimonials            → All testimonials"
      ]
    });

  } catch (err) {
    return jsonResponse({ success: false, error: err.message }, 500);
  }
}

/**
 * Converts a sheet into an array of objects.
 * Automatically filters rows based on query params (e.g. active=true, type=dog).
 */
function getSheetAsArray(ss, sheetName, params) {
  const sheet = ss.getSheetByName(sheetName);
  if (!sheet) throw new Error(`Sheet "${sheetName}" not found`);

  const dataRange = sheet.getDataRange();
  const values = dataRange.getValues();

  if (values.length < 2) return []; // No data rows

  const headers = values[0].map(h => String(h).trim());
  const rows = values.slice(1);

  const result = [];

  for (let i = 0; i < rows.length; i++) {
    const row = rows[i];
    const obj = {};
    let hasData = false;

    headers.forEach((header, colIndex) => {
      if (!header) return;
      let val = row[colIndex];

      // Convert TRUE/FALSE strings to real booleans
      if (typeof val === 'string') {
        const upper = val.toUpperCase().trim();
        if (upper === 'TRUE') val = true;
        else if (upper === 'FALSE') val = false;
      }

      obj[header] = val;
      if (val !== '' && val !== null && val !== undefined) hasData = true;
    });

    if (!hasData) continue; // skip completely empty rows

    // Apply simple filters from query params
    let include = true;
    Object.keys(params).forEach(key => {
      if (key === 'sheet' || key === 'all' || key === 'nocache') return;

      const filterValue = params[key];
      if (obj.hasOwnProperty(key)) {
        const rowValue = obj[key];
        // Coerce comparison
        if (String(rowValue).toLowerCase() !== String(filterValue).toLowerCase()) {
          include = false;
        }
      }
    });

    if (include) {
      result.push(obj);
    }
  }

  // Sort by sort_order if the column exists
  if (result.length > 0 && result[0].hasOwnProperty('sort_order')) {
    result.sort((a, b) => (a.sort_order || 999) - (b.sort_order || 999));
  }

  return result;
}

/**
 * Special helper for the Settings sheet → returns a clean key/value object.
 */
function getSettingsAsObject(ss) {
  const sheet = ss.getSheetByName('Settings');
  if (!sheet) return {};

  const values = sheet.getDataRange().getValues();
  const obj = {};

  for (let i = 1; i < values.length; i++) {
    const key = String(values[i][0] || '').trim();
    const value = values[i][1];
    if (key) obj[key] = value;
  }
  return obj;
}

/**
 * Helper to return proper JSON with CORS headers.
 */
function jsonResponse(obj, statusCode = 200) {
  const output = ContentService.createTextOutput(JSON.stringify(obj, null, 2));
  output.setMimeType(ContentService.MimeType.JSON);

  // Important for static sites / file:// testing and cross-origin requests
  return output;
}

/**
 * Optional: Clear the entire cache (useful during development).
 * Call this manually from the Apps Script editor if needed.
 */
function clearCache() {
  CacheService.getScriptCache().removeAll(['all_content']);
  console.log('Cache cleared');
}
