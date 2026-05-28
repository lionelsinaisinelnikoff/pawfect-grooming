# Pawfect Grooming — Content Management Backend

A simple, self-hosted backend that lets you fully control the website content (text, images, videos, services, team, gallery, etc.) through a beautiful admin panel — no Google Sheets required.

## Features
- Password-protected admin panel
- Live editing of hero, about, services, team, gallery, testimonials, and settings
- Upload new images and videos directly from the admin
- Changes are saved to `data/content.json`
- The public website can optionally pull live content when the backend is running
- Works completely locally

## Quick Start

1. **Install dependencies** (one time):
   ```bash
   cd backend
   pip3 install flask flask-cors python-dotenv
   ```

2. **Start the backend**:
   ```bash
   python3 server.py
   ```

3. **Access the admin panel**:
   - Open http://localhost:5050/admin in your browser
   - Default password: `admin123` (change this in `server.py`)

4. **View the live site while the backend is running**:
   - In a separate terminal, run: `python3 -m http.server 8000`
   - Then open http://localhost:8000 in your browser
   - Click **"View Site"** in the admin — it's now smart and will open your local site (or fall back to the published demo)

5. **Access the admin from the site**:
   - Scroll to the very bottom of the footer
   - Click **"ADMIN PANEL"**
   - It will open http://localhost:5050/admin in a new tab (backend must be running)

## How It Works

- All editable content lives in `backend/data/content.json`
- Uploaded media goes into `backend/uploads/`
- The public `index.html` tries to fetch from `http://localhost:5050/api/content` on load when the backend is running (graceful fallback to static content)
- The dedicated `/admin` interface gives you full control with a nice UI

## Changing the Password

Edit the top of `backend/server.py`:

```python
DEFAULT_ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "your-new-password-here")
```

You can also set an environment variable `ADMIN_PASSWORD` when starting the server.

## Production Notes

This is a local/development tool. For real production use you would want:
- Proper user accounts + hashed passwords
- HTTPS
- Regular backups of `data/`
- Possibly a reverse proxy (nginx) + process manager (pm2 / systemd)

For now it gives you complete control over your beautiful static site with almost zero friction.

## 💳 Stripe Integration

The backend now powers real payments for the booking form.

**Required environment variables for payments:**

| Variable                | Required | Description                              |
|-------------------------|----------|------------------------------------------|
| `STRIPE_SECRET_KEY`     | Yes      | Your Stripe secret key (`sk_test_...` or `sk_live_...`) |
| `STRIPE_WEBHOOK_SECRET` | Optional | Webhook signing secret for `/api/webhook/stripe` |

**Endpoints added:**

- `POST /api/create-checkout-session` — Creates a Stripe Checkout Session. Frontend calls this with booking details.
- `GET /api/bookings` — Returns recent paid bookings (shown in admin).
- `POST /api/webhook/stripe` — Stripe webhook handler (strongly recommended).

**Test card (Stripe test mode):** `4242 4242 4242 4242` + any future expiry + any CVC.

Bookings are stored in `data/bookings.json` and visible in the admin under the new **Bookings** tab.

Enjoy managing your content the easy way. 🐾
