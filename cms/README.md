# Pawfect Grooming — Google Sheets CMS

A lightweight, no-code Content Management System powered by Google Sheets + Google Apps Script. Perfect for static sites that need an easy way for non-technical people (or pet-loving owners) to update services, team, gallery, and testimonials without touching code.

This kit is tailored specifically for **Pawfect Grooming**.

---

## What You Get

- 5 purpose-built Google Sheets tabs with clean schemas
- A production-ready JSON API (via Google Apps Script Web App)
- Browser-friendly JavaScript helper (`pawfect-cms.js`)
- Realistic sample data that matches the current static site
- Full setup instructions + demo page

---

## Sheet Structure

### 1. Settings
Simple key/value store for global site data.

| key                    | Example value                              |
|------------------------|--------------------------------------------|
| site_name              | Pawfect Grooming                           |
| tagline                | Love your pet. Let us pamper them.         |
| address                | 1248 Pearl Street, Boulder, Colorado 80302 |
| phone                  | 888-888-888                                |
| email                  | hello@pawfectgrooming.com                  |
| hours                  | Tuesday – Friday: 8:00 AM – 6:00 PM...     |
| booking_notice         | We typically book 1–3 weeks out...         |
| instagram_url          | https://instagram.com/pawfectgrooming      |
| years_experience       | 12                                         |
| pets_pampered          | 4800                                       |
| review_pct             | 98                                         |
| groomer_count          | 3                                          |
| founder_name           | Sarah Kline                                |
| founder_quote          | "Every pet who walks..."                   |

### 2. Services
All grooming offerings.

Columns:
- `id`
- `name`
- `price_label` (e.g. "FROM $95", "$55")
- `duration` (e.g. "60–90 min")
- `description`
- `icon` (spa, shower, cut, hand-sparkles, tooth, wind)
- `sort_order`
- `active` (TRUE/FALSE)

### 3. Groomers
Your team members.

Columns:
- `id`
- `name`
- `title`
- `bio`
- `years` (e.g. "12")
- `photo_filename` — e.g. `images/groomer-sarah.jpg`
- `sort_order`
- `active`

### 4. Gallery
Pet photos for the gallery grid.

Columns:
- `id`
- `filename` — e.g. `images/pomeranian.jpg`
- `alt`
- `caption`
- `type` — "dog" or "cat"
- `sort_order`
- `active`

### 5. Testimonials
Client love notes.

Columns:
- `id`
- `quote`
- `author`
- `pet_info` (e.g. "Luna (Pomeranian)")
- `rating` (5 or 4.5)
- `sort_order`
- `active`

---

## Quick Start (5–7 minutes)

### Step 1: Create the Google Sheet

1. Go to [sheets.new](https://sheets.new)
2. Rename the default tab to **Settings**
3. Create 4 more tabs:
   - Services
   - Groomers
   - Gallery
   - Testimonials

### Step 2: Add Headers + Sample Data

Copy the headers and data from the `sample-data/` folder into each tab.

**Tip**: In Google Sheets, paste the data starting from cell A1. The first row must be the exact column headers.

You can also use **File → Import → Upload** and select each .csv file.

### Step 3: Install the Apps Script

1. In your Google Sheet, go to **Extensions → Apps Script**
2. Delete the default `Code.gs` content
3. Copy the entire contents of `apps-script/Code.gs` and paste it in
4. Click the **Save** icon

### Step 4: Deploy as Web App

1. Click **Deploy** → **New deployment**
2. In the dropdown at the top, choose **Web app**
3. Configure:
   - **Execute as**: `Me` (your account)
   - **Who has access**: `Anyone`
4. Click **Deploy**
5. **Authorize** the script when prompted (only needs to happen once)
6. Copy the **Deployment ID** or the full Web App URL:
   `https://script.google.com/macros/s/AKfycbx.../exec`

> **Important**: Every time you change the Apps Script code, you must **Deploy → Manage deployments → Edit** (or create a new version) for changes to take effect.

### Step 5: Test the API

Open this URL in your browser (replace with your real deployment URL):

```
https://script.google.com/macros/s/YOUR_DEPLOYMENT_ID/exec?all=true
```

You should see a big JSON object with `Settings`, `Services`, `Groomers`, `Gallery`, and `Testimonials`.

Other useful endpoints:
- `?sheet=Services&active=true`
- `?sheet=Gallery&type=dog`
- `?sheet=Groomers`

---

## Using the Data on Your Website

### Option A — Use the provided JavaScript helper (recommended)

Add this before the closing `</body>` tag in `index.html`:

```html
<script src="cms/pawfect-cms.js"></script>
<script>
  const cms = new PawfectCMS("https://script.google.com/macros/s/YOUR_DEPLOYMENT_ID/exec");

  // Fetch everything
  const data = await cms.getAll();

  // Or fetch individual collections
  const services = await cms.get("Services", { active: true });
  const groomers = await cms.get("Groomers", { active: true });
</script>
```

### Option B — Plain fetch

```js
const res = await fetch(
  "https://script.google.com/macros/s/YOUR_ID/exec?sheet=Services&active=true"
);
const services = await res.json();
```

See `demo.html` in this folder for a complete working example of rendering.

---

## Wiring It Into the Pawfect Grooming Site

The current `index.html` is a beautiful static site. The recommended path is **progressive enhancement**:

1. Keep the existing HTML as the default (works with JS disabled, instant load, great for SEO)
2. Add a small loader script that (when CMS is enabled) fetches data and replaces:
   - Services grid
   - Team/Groomers section
   - Gallery images + filters
   - Testimonials
   - Phone numbers, address, hours, trust bar stats, etc.

A ready-to-use dynamic loader can be added by editing the JavaScript section in `index.html` (see comments in the file).

---

## Caching & Performance

The Apps Script uses `CacheService` (5-minute default). This keeps responses fast and reduces Google quota usage.

- Change `CACHE_TTL_SECONDS` in `Code.gs` to `0` during development for instant updates.
- Append `&nocache=1` to any request during testing to bypass cache.

---

## Updating Content

1. Just edit the Google Sheet like a normal spreadsheet.
2. Changes appear on the live site within ~5 minutes (or immediately if you redeploy or use `nocache`).
3. No rebuilds, no Git deploys, no FTP — just save the sheet.

---

## Security Notes

- The Web App is intentionally public (`Anyone`).
- Never put passwords, customer data, or private info in these sheets.
- Keep the actual Google Sheet private or share edit access only with trusted people.
- The public only sees what your API returns.

---

## Want More Sheets?

Common additions:
- `Faqs`
- `Addons` (extra services)
- `BlogPosts`
- `SeoMeta`

Just add a new tab — the `?sheet=NewTabName` endpoint will automatically work.

---

## Need Help?

This kit was built to make Pawfect Grooming easy to maintain for years.

If you want:
- A fully dynamic `index.html` that always pulls from the CMS (no static fallback)
- An admin-friendly UI on top of Sheets
- Image uploads handled via Google Drive
- Booking form that writes leads back into a "Leads" sheet

…just ask and we can extend it.

---

**You now have a real, free CMS without paying for Webflow, Contentful, or Sanity.**

Enjoy the simplicity — and give those pups the pampering they deserve.

---

Built with ❤️ and Grok • 2026
