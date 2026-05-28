/**
 * PawfectCMS — Clean client for the Google Sheets CMS (Pawfect Grooming)
 *
 * Usage:
 *   const cms = new PawfectCMS("https://script.google.com/macros/s/YOUR_DEPLOYMENT_ID/exec");
 *
 *   const allData = await cms.getAll();
 *   const services = await cms.get("Services", { active: true });
 *   const groomers = await cms.get("Groomers", { active: true });
 *   const dogGallery = await cms.get("Gallery", { type: "dog" });
 */
class PawfectCMS {
  /**
   * @param {string} apiBaseUrl - The full Web App URL ending in /exec
   */
  constructor(apiBaseUrl) {
    if (!apiBaseUrl || !apiBaseUrl.includes('/exec')) {
      throw new Error('PawfectCMS requires a valid Google Apps Script Web App URL (ending in /exec)');
    }
    this.baseUrl = apiBaseUrl.replace(/\/$/, ''); // remove trailing slash
    this._cache = new Map(); // very short-lived in-memory cache
  }

  /**
   * Fetch everything in one call (Settings, Services, Groomers, Gallery, Testimonials)
   * @param {object} options
   * @returns {Promise<object>}
   */
  async getAll(options = {}) {
    const url = this._buildUrl({ all: true, ...options });
    return this._fetch(url, 'all');
  }

  /**
   * Fetch a single sheet with optional filters.
   *
   * Examples:
   *   cms.get("Services")
   *   cms.get("Gallery", { type: "dog", active: true })
   *   cms.get("Groomers", { active: true })
   *   cms.get("Testimonials", { active: true })
   *
   * @param {string} sheetName
   * @param {object} filters - key/value pairs that become query params
   * @returns {Promise<Array>}
   */
  async get(sheetName, filters = {}) {
    const params = { sheet: sheetName, ...filters };
    const url = this._buildUrl(params);
    return this._fetch(url, sheetName);
  }

  /**
   * Fetch Settings as a clean object { key: value }
   */
  async getSettings() {
    const data = await this.get('Settings');
    const obj = {};
    data.forEach(row => {
      if (row.key) obj[row.key] = row.value;
    });
    return obj;
  }

  // --- Internal helpers ---

  _buildUrl(params) {
    const query = Object.entries(params)
      .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
      .join('&');
    return `${this.baseUrl}?${query}`;
  }

  async _fetch(url, cacheKey) {
    // Tiny in-memory cache (30s) to avoid hammering the API on the same page
    const cached = this._cache.get(cacheKey);
    if (cached && Date.now() - cached.time < 30000) {
      return cached.data;
    }

    const res = await fetch(url, {
      method: 'GET',
      headers: { 'Accept': 'application/json' }
    });

    if (!res.ok) {
      throw new Error(`CMS request failed: ${res.status} ${res.statusText}`);
    }

    const json = await res.json();

    if (!json.success) {
      throw new Error(json.error || 'Unknown CMS error');
    }

    let payload;
    if (json.data) {
      payload = json.data; // single sheet
    } else {
      payload = json; // full response (getAll)
    }

    this._cache.set(cacheKey, { data: payload, time: Date.now() });
    return payload;
  }
}

// Make it available both as ES module and global
if (typeof window !== 'undefined') {
  window.PawfectCMS = PawfectCMS;
}
if (typeof module !== 'undefined') {
  module.exports = PawfectCMS;
}
