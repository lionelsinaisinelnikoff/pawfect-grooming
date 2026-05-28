# Pawfect Grooming

A beautiful, premium single-page website for a fictional pet grooming studio in Boulder, Colorado — with a full **self-hosted admin backend** for easy content management.

**Live Demo (static site):** [https://lionelsinaisinelnikoff.github.io/pawfect-grooming](https://lionelsinaisinelnikoff.github.io/pawfect-grooming)

---

## ✨ Features

- Modern, luxury aesthetic with warm cream, sage, and terracotta color palette
- Fully responsive (mobile-first design with hamburger menu)
- Interactive gallery with category filtering (All / Dogs / Cats) and lightbox modal
- 6 detailed service offerings with pricing
- "Select Service" buttons that auto-scroll and pre-fill the booking form
- Fully functional booking form (simulated submission with success modal)
- Meet the Team section with 4 groomers
- Customer testimonials
- **Full self-hosted admin backend** (Flask) — login from the footer to edit content, upload images/videos, and manage services/team/gallery live
- Legacy optional Google Sheets CMS also included for comparison

## 🖼️ Images & Videos

- All 12 original hero/gallery/team images were generated using **Grok Imagine**.
- **5 new short looping videos** were generated with the xAI Video model and integrated for premium motion.
- Full **self-hosted content management backend** with login (accessible from footer "Admin Login"). Edit texts, services, team, gallery, upload new images/videos, etc. See `backend/README.md`.
  - Hero background (cinematic wide grooming scene)
  - About section (Sarah gently caring for a Golden)
  - 3 gallery highlights (happy dogs group, detailed pawdicure, transformation grooming)
- Videos use the original JPGs as `poster` fallbacks, are muted + looping in the grid, and support sound + controls in the lightbox.
- Total video payload kept reasonable (~11 MB).

## 🛠️ Tech Stack

- Pure HTML5 + Tailwind CSS (via CDN)
- Vanilla JavaScript (no frameworks)
- Font Awesome icons
- Optional self-hosted backend (Python + Flask) with login-protected admin panel for real content management
- Can also run 100% static (no backend required)

## 📁 Project Structure

```
pawfect-grooming/
├── index.html                 # Main site (now featuring premium video moments)
├── images/                    # 12 custom-generated images (also used as video posters)
├── videos/                    # 5 Grok-generated short looping video clips
├── backend/                   # Self-hosted CMS with login (recommended)
│   ├── server.py
│   ├── data/content.json
│   ├── uploads/
│   └── README.md
├── cms/                       # Legacy Google Sheets CMS kit (optional)
├── README.md
└── .gitignore
```

## 🚀 Running Locally

Simply open `index.html` in any modern browser:

```bash
open index.html
```

Or serve it:

```bash
# Python
python3 -m http.server 8000

# npx
npx serve .
```

## 🔧 Self-Hosted Admin Backend (Recommended for Dynamic Updates)

The project includes a complete local admin system:

- Run `python3 backend/server.py`
- Click **ADMIN PANEL** in the site footer
- Edit text, services, team, testimonials, and upload new images/videos
- All changes saved to `backend/data/content.json`
- The static site can optionally load live content from the backend when it's running

See `backend/README.md` for full instructions.

## 💳 Stripe Payments (New!)

The booking form now supports **real payments** via Stripe Checkout.

### Quick Setup (Local)

1. **Install the Stripe Python library**
   ```bash
   cd backend
   pip3 install stripe
   ```

2. **Get your Stripe test keys**
   - Go to https://dashboard.stripe.com/test/apikeys
   - Copy **Publishable key** (starts with `pk_test_...`) and **Secret key** (`sk_test_...`)

3. **Run the backend with Stripe enabled**
   ```bash
   STRIPE_SECRET_KEY=sk_test_xxxxxxxxxxxxxxxx  python3 backend/server.py
   ```

4. **Test the flow**
   - Open the site (`python3 -m http.server 8000`)
   - Click any "SELECT SERVICE" button
   - Fill out the booking form and submit
   - You'll be redirected to Stripe's secure checkout (use test card `4242 4242 4242 4242`)

5. **(Optional but recommended)** Set up the webhook for reliable booking recording:
   - In Stripe Dashboard → Developers → Webhooks → Add endpoint: `http://localhost:5050/api/webhook/stripe`
   - Copy the **Signing secret** and run with:
     ```bash
     STRIPE_SECRET_KEY=sk_test_... STRIPE_WEBHOOK_SECRET=whsec_... python3 backend/server.py
     ```

After a successful payment, bookings appear in the **Admin Panel → Bookings** tab.

For production, set the same environment variables on your server and update the success/cancel URLs in `server.py` if needed.

## 🔄 Legacy: Google Sheets CMS (Optional)

The site ships static by default for speed, simplicity, and perfect Lighthouse scores. However, a complete **Google Sheets CMS kit** is included in the `cms/` folder.

### Why this approach?
- Non-technical owners can edit prices, add new groomers, update photos, and change testimonials in a spreadsheet
- No rebuilds or deploys needed after the initial setup
- 5-minute cache keeps everything fast
- Works beautifully with GitHub Pages, Netlify, Vercel, or any static host

### Quick start
1. Follow the step-by-step guide in [cms/README.md](cms/README.md)
2. Create a Google Sheet with the 5 tabs
3. Paste in the sample CSVs from `cms/sample-data/`
4. Deploy the included `apps-script/Code.gs` as a Web App
5. (Optional) Wire the `PawfectCMS` client into `index.html` to replace the static sections

A working preview page exists at `cms/demo.html` — just replace the placeholder URL with your own deployment URL.

Once connected, changing a price or adding a new testimonial in the sheet instantly updates the live website (within cache window).

---

## 📝 Notes

This project was created as a demonstration of building a polished, production-ready marketing site quickly using modern tools and AI-generated imagery, with an optional enterprise-grade (but free) content management layer.

All business details (name, address, phone, team members) are fictional.

## 📄 License

This project is available for personal and educational use.

---

Built with ❤️ and Grok in 2026.