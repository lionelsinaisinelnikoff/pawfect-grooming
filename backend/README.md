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
   - Open http://localhost:5000/admin in your browser
   - Default password: `admin123` (change this in `server.py`)

4. **On the live site**:
   - Scroll to the very bottom of the footer
   - Click the tiny **"ADMIN LOGIN"** link
   - It will open the full admin in a new tab (backend must be running)

## How It Works

- All editable content lives in `backend/data/content.json`
- Uploaded media goes into `backend/uploads/`
- The public `index.html` tries to fetch from `http://localhost:5000/api/content` on load (graceful fallback to static content)
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

Enjoy managing your content the easy way. 🐾
