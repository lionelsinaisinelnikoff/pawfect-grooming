#!/usr/bin/env python3
"""
Pawfect Grooming - Content Management Backend
Simple, self-contained Flask server with login-protected admin.

Run with:
    python3 backend/server.py

Then visit: http://localhost:5050/admin
"""

import os
import json
import secrets
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import (
    Flask, request, jsonify, session, redirect, url_for,
    send_from_directory, render_template_string
)
from flask_cors import CORS
from werkzeug.utils import secure_filename

# ---------------- CONFIG ----------------
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = BASE_DIR / "uploads"
CONTENT_FILE = DATA_DIR / "content.json"
BOOKINGS_FILE = DATA_DIR / "bookings.json"

# Change this password on first run (or set ADMIN_PASSWORD env var)
DEFAULT_ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))

# Stripe configuration (set these in your environment for live or test)
# Support multiple common env var names for convenience
STRIPE_SECRET_KEY = (
    os.environ.get("STRIPE_SECRET_KEY")
    or os.environ.get("stripe_secret_key")
    or os.environ.get("STRIPE_SECRET")
    or os.environ.get("stripeSecretKey")
    or ""
)
STRIPE_WEBHOOK_SECRET = (
    os.environ.get("STRIPE_WEBHOOK_SECRET")
    or os.environ.get("stripe_webhook_secret")
    or ""
)

try:
    import stripe
    if STRIPE_SECRET_KEY:
        stripe.api_key = STRIPE_SECRET_KEY
except ImportError:
    stripe = None

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "mp4", "mov", "webm"}

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB max upload

CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# Ensure folders exist
DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)


# ---------------- HELPERS ----------------
def load_content():
    if CONTENT_FILE.exists():
        with open(CONTENT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_content(data):
    data["meta"]["lastUpdated"] = datetime.utcnow().isoformat() + "Z"
    with open(CONTENT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return data


# --- Stripe / Booking Helpers ---

def get_service_price_cents(service_name: str) -> int:
    """Look up price from content.json services. Falls back to sensible defaults."""
    content = load_content()
    services = content.get("services", [])

    for svc in services:
        if svc.get("name") == service_name:
            price = svc.get("priceCents")
            if isinstance(price, int) and price > 0:
                return price

    # Fallback defaults (in cents)
    defaults = {
        "Signature Full Groom": 12500,
        "Bath & Brush Out": 5500,
        "Haircut & Styling": 7500,
        "Pawdicure & Nail Trim": 3500,
        "Dental Care Treatment": 2800,
        "De-Shedding Spa Treatment": 6500,
        "Custom / Multiple Services": 5000,  # $50 deposit for customs
    }
    return defaults.get(service_name, 7500)


def load_bookings():
    if BOOKINGS_FILE.exists():
        try:
            with open(BOOKINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_booking(booking: dict):
    bookings = load_bookings()
    booking["id"] = f"bk_{int(datetime.utcnow().timestamp())}"
    booking["createdAt"] = datetime.utcnow().isoformat() + "Z"
    bookings.insert(0, booking)  # newest first
    # Keep only last 200
    if len(bookings) > 200:
        bookings = bookings[:200]
    with open(BOOKINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(bookings, f, indent=2)
    return booking


def record_paid_booking(session_data: dict):
    """Store a successfully paid booking from Stripe metadata."""
    meta = session_data.get("metadata", {})
    booking = {
        "status": "paid",
        "stripeSessionId": session_data.get("id"),
        "amountTotal": session_data.get("amount_total"),
        "customerEmail": session_data.get("customer_email") or meta.get("ownerEmail"),
        "ownerName": meta.get("ownerName"),
        "petName": meta.get("petName"),
        "service": meta.get("service"),
        "preferredDate": meta.get("preferredDate"),
        "preferredTime": meta.get("preferredTime"),
        "phone": meta.get("ownerPhone"),
        "notes": meta.get("notes"),
        "petType": meta.get("petType"),
        "petBreed": meta.get("petBreed"),
    }
    return save_booking(booking)


# --- Media Library Helpers ---
def get_media_library():
    content = load_content()
    return content.get("mediaLibrary", {})


def get_media_item(media_id):
    library = get_media_library()
    return library.get(media_id)


def add_media_to_library(media_id, media_item):
    content = load_content()
    if "mediaLibrary" not in content:
        content["mediaLibrary"] = {}
    content["mediaLibrary"][media_id] = media_item
    save_content(content)
    return media_item


def assign_media_to_element(media_id, element_type, element_id=None):
    """
    Assigns a media item to a specific part of the site.
    element_type: 'hero', 'about', 'team', 'service', 'gallery'
    """
    content = load_content()
    library = content.setdefault("mediaLibrary", {})

    if media_id not in library:
        return False, "Media item not found"

    media_item = library[media_id]

    if element_type == "hero":
        content.setdefault("hero", {})["backgroundMediaId"] = media_id

    elif element_type == "about":
        content.setdefault("about", {})["featuredMediaId"] = media_id

    elif element_type == "team" and element_id is not None:
        for member in content.get("team", []):
            if str(member.get("id")) == str(element_id):
                member["photoMediaId"] = media_id
                break

    elif element_type == "service" and element_id is not None:
        for service in content.get("services", []):
            if str(service.get("id")) == str(element_id):
                service["imageMediaId"] = media_id
                break

    elif element_type == "gallery" and element_id is not None:
        for item in content.get("gallery", []):
            if str(item.get("id")) == str(element_id):
                item["mediaId"] = media_id
                break

    save_content(content)
    return True, "Assigned successfully"


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function


# ---------------- PUBLIC API ----------------
@app.route("/api/content", methods=["GET"])
def get_content():
    """Public endpoint - used by the live website"""
    content = load_content()
    return jsonify(content)


# ---------------- STRIPE BOOKING PAYMENTS ----------------

@app.route("/api/create-checkout-session", methods=["POST"])
def create_checkout_session():
    """Create a Stripe Checkout Session for a grooming booking."""
    if not stripe or not STRIPE_SECRET_KEY:
        return jsonify({
            "error": "Stripe is not configured on this server. Set STRIPE_SECRET_KEY environment variable."
        }), 503

    data = request.get_json() or {}

    service = data.get("service", "").strip()
    owner_name = data.get("ownerName", "").strip()
    owner_email = data.get("ownerEmail", "").strip()
    owner_phone = data.get("ownerPhone", "").strip()
    pet_name = data.get("petName", "").strip()
    pet_type = data.get("petType", "").strip()
    pet_breed = data.get("petBreed", "").strip()
    preferred_date = data.get("preferredDate", "").strip()
    preferred_time = data.get("preferredTime", "").strip()
    notes = data.get("notes", "").strip()

    if not service or not owner_email or not owner_name or not pet_name:
        return jsonify({"error": "Missing required fields (service, ownerName, ownerEmail, petName)"}), 400

    amount_cents = get_service_price_cents(service)

    # Build a clean success/cancel URL (works for local dev + production)
    # In production you would use your real domain.
    origin = request.headers.get("Origin") or "http://localhost:8000"
    success_url = f"{origin}/?paid=success&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/?paid=cancel"

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"Pawfect Grooming — {service}",
                        "description": f"Appointment for {pet_name} ({pet_type}) on {preferred_date} at {preferred_time}",
                        "metadata": {"service": service}
                    },
                    "unit_amount": amount_cents,
                },
                "quantity": 1,
            }],
            customer_email=owner_email if owner_email else None,
            metadata={
                "ownerName": owner_name,
                "ownerEmail": owner_email,
                "ownerPhone": owner_phone,
                "petName": pet_name,
                "petType": pet_type,
                "petBreed": pet_breed,
                "service": service,
                "preferredDate": preferred_date,
                "preferredTime": preferred_time,
                "notes": notes[:500] if notes else "",
            },
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return jsonify({"url": session.url, "sessionId": session.id})
    except Exception as e:
        return jsonify({"error": f"Stripe error: {str(e)}"}), 500


@app.route("/api/bookings", methods=["GET"])
def list_bookings():
    """Public for now (in real app you'd protect this). Returns recent paid bookings."""
    bookings = load_bookings()
    return jsonify(bookings[:50])


@app.route("/api/webhook/stripe", methods=["POST"])
def stripe_webhook():
    """Handle Stripe webhook events (recommended for production fulfillment)."""
    if not stripe or not STRIPE_WEBHOOK_SECRET:
        return jsonify({"error": "Webhook not configured"}), 503

    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        return jsonify({"error": f"Invalid signature: {str(e)}"}), 400

    if event["type"] == "checkout.session.completed":
        session_obj = event["data"]["object"]
        try:
            record_paid_booking(session_obj)
        except Exception as e:
            print("Failed to record booking:", e)

    return jsonify({"received": True})


# ---------------- AUTH ----------------
@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    password = data.get("password", "")

    if password == DEFAULT_ADMIN_PASSWORD:
        session["logged_in"] = True
        session.permanent = True
        return jsonify({"success": True, "message": "Logged in successfully"})
    else:
        return jsonify({"success": False, "error": "Invalid password"}), 401


@app.route("/api/logout", methods=["POST"])
def logout():
    session.pop("logged_in", None)
    return jsonify({"success": True})


@app.route("/api/auth/status", methods=["GET"])
def auth_status():
    return jsonify({"loggedIn": bool(session.get("logged_in"))})


# ---------------- PROTECTED CONTENT MANAGEMENT ----------------
@app.route("/api/content", methods=["POST"])
@login_required
def update_content():
    """Replace the entire content object (or merge if ?merge=true)"""
    try:
        new_data = request.get_json()
        if not new_data:
            return jsonify({"error": "No JSON data provided"}), 400

        current = load_content()

        merge = request.args.get("merge", "false").lower() == "true"
        if merge:
            # Deep merge for convenience (simple implementation)
            def deep_merge(base, updates):
                for key, value in updates.items():
                    if isinstance(value, dict) and key in base:
                        deep_merge(base[key], value)
                    else:
                        base[key] = value
                return base
            updated = deep_merge(current, new_data)
        else:
            updated = new_data

        save_content(updated)
        return jsonify({"success": True, "message": "Content updated", "lastUpdated": updated["meta"]["lastUpdated"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------- MEDIA UPLOADS (with optional assignment) ----------------
@app.route("/api/upload", methods=["POST"])
@login_required
def upload_media():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "File type not allowed"}), 400

    filename = secure_filename(file.filename)
    stem, ext = os.path.splitext(filename)
    counter = 1
    final_name = filename
    while (UPLOAD_DIR / final_name).exists():
        final_name = f"{stem}-{counter}{ext}"
        counter += 1

    filepath = UPLOAD_DIR / final_name
    file.save(filepath)

    media_type = "video" if ext.lower() in {".mp4", ".mov", ".webm"} else "image"
    media_id = f"m_{int(datetime.utcnow().timestamp())}_{stem[:8]}"

    media_item = {
        "id": media_id,
        "filename": final_name,
        "type": media_type,
        "url": f"/media/{final_name}",
        "poster": None,
        "originalName": file.filename,
        "uploadedAt": datetime.utcnow().isoformat() + "Z"
    }

    add_media_to_library(media_id, media_item)

    # Optional immediate assignment
    assign_type = request.form.get("assign_to_type")
    assign_id = request.form.get("assign_to_id")

    assigned = False
    if assign_type:
        success, msg = assign_media_to_element(media_id, assign_type, assign_id)
        assigned = success

    return jsonify({
        "success": True,
        "mediaId": media_id,
        "filename": final_name,
        "url": f"/media/{final_name}",
        "type": media_type,
        "assigned": assigned,
        "assignType": assign_type,
        "assignId": assign_id
    })


@app.route("/api/media/assign", methods=["POST"])
@login_required
def assign_media_route():
    data = request.get_json() or {}
    success, message = assign_media_to_element(
        data.get("mediaId"),
        data.get("elementType"),
        data.get("elementId")
    )
    if success:
        return jsonify({"success": True, "message": message})
    return jsonify({"success": False, "error": message}), 400


@app.route("/api/media", methods=["GET"])
@login_required
def list_media():
    """List all media. Always scans the uploads folder so the admin never looks empty.
    Enriches with data from mediaLibrary when available.
    """
    content = load_content()
    library = content.get("mediaLibrary", {})

    # First, collect everything from the physical uploads folder
    discovered = {}
    for f in sorted(UPLOAD_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if not f.is_file() or not allowed_file(f.name):
            continue
        ext = f.suffix.lower()
        mtype = "video" if ext in {".mp4", ".mov", ".webm"} else "image"
        discovered[f.name] = {
            "filename": f.name,
            "url": f"/media/{f.name}",
            "type": mtype,
            "size": f.stat().st_size,
            "uploadedAt": datetime.fromtimestamp(f.stat().st_mtime).isoformat() + "Z",
            "originalName": f.name
        }

    # Merge with mediaLibrary data (prefer library metadata)
    media_list = []
    for filename, file_info in discovered.items():
        # Find matching entry in mediaLibrary (by filename)
        matching_entry = None
        matching_id = None
        for mid, item in library.items():
            if item.get("filename") == filename:
                matching_entry = item
                matching_id = mid
                break

        if matching_entry:
            item = {**file_info, **matching_entry}  # library data wins
            item["id"] = matching_id
        else:
            item = file_info
            item["id"] = f"m_file_{filename.replace('.', '_')}"

        # Usage detection (works whether from library or not)
        usage = []
        mid = item.get("id")
        if content.get("hero", {}).get("backgroundMediaId") == mid:
            usage.append({"type": "hero", "label": "Hero Background"})
        if content.get("about", {}).get("featuredMediaId") == mid:
            usage.append({"type": "about", "label": "About Section"})
        for member in content.get("team", []):
            if member.get("photoMediaId") == mid:
                usage.append({"type": "team", "id": member["id"], "label": member["name"]})
        for svc in content.get("services", []):
            if svc.get("imageMediaId") == mid:
                usage.append({"type": "service", "id": svc["id"], "label": svc["name"]})
        for gal in content.get("gallery", []):
            if gal.get("mediaId") == mid:
                usage.append({"type": "gallery", "id": gal["id"], "label": gal.get("caption", "Gallery Item")})

        item["usage"] = usage
        media_list.append(item)

    # Also include any library entries whose files might have been deleted (so user can clean up)
    for mid, item in library.items():
        if item.get("filename") not in discovered:
            item = dict(item)
            item["id"] = mid
            item["usage"] = []  # can't compute easily
            item["missing"] = True
            media_list.append(item)

    media_list.sort(key=lambda x: x.get("uploadedAt", ""), reverse=True)
    return jsonify(media_list)


# Serve uploaded media
@app.route("/media/<path:filename>")
def serve_media(filename):
    return send_from_directory(UPLOAD_DIR, filename)


# ---------------- ADMIN UI ----------------
ADMIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pawfect Grooming — Admin</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        body { font-family: 'Inter', system_ui, sans-serif; }
        .heading-serif { font-family: 'Playfair Display', Georgia, serif; font-weight: 700; }
        .section-card { transition: all 0.2s ease; }
        .media-item { transition: transform 0.2s ease; }
        .media-item:hover { transform: scale(1.02); }
    </style>
</head>
<body class="bg-[#FDF8F4] text-[#2F3A3A]">
    <div class="max-w-7xl mx-auto p-6">
        <!-- Header -->
        <div class="flex items-center justify-between mb-8">
            <div class="flex items-center gap-x-4">
                <div class="w-11 h-11 bg-gradient-to-br from-[#A67C6D] to-[#5C7A6E] rounded-2xl flex items-center justify-center">
                    <i class="fa-solid fa-paw text-white text-3xl"></i>
                </div>
                <div>
                    <span class="font-bold text-3xl tracking-tighter heading-serif">Pawfect</span>
                    <span class="text-[#A67C6D] text-sm block -mt-1 tracking-[2px]">ADMIN PANEL</span>
                </div>
            </div>
            <div class="flex items-center gap-x-3">
                <button onclick="viewSite()" class="px-4 py-2 text-sm font-medium hover:bg-white rounded-2xl border border-[#EDE4DB]">View Site</button>
                <button onclick="logout()" 
                        class="px-5 py-2.5 bg-[#2F3A3A] hover:bg-black text-white text-sm font-semibold rounded-2xl flex items-center gap-x-2">
                    <i class="fa-solid fa-sign-out-alt"></i>
                    <span>Logout</span>
                </button>
            </div>
        </div>

        <div id="login-screen" class="max-w-md mx-auto mt-20 hidden">
            <div class="bg-white border border-[#EDE4DB] rounded-3xl p-8 shadow-xl">
                <h2 class="text-2xl font-semibold heading-serif tracking-tight">Admin Login</h2>
                <p class="text-[#2F3A3A]/70 mt-2">Enter the admin password to manage the website.</p>
                
                <div class="mt-6">
                    <input id="password-input" type="password" placeholder="Password" 
                           class="w-full border border-[#EDE4DB] bg-[#FDF8F4] rounded-2xl px-5 h-14 text-base focus:outline-none focus:border-[#A67C6D]">
                    <button onclick="performLogin()" 
                            class="mt-4 w-full h-14 bg-[#A67C6D] hover:bg-[#8F685C] text-white font-semibold rounded-2xl">
                        Sign In
                    </button>
                    <p id="login-error" class="text-red-600 text-sm mt-3 hidden"></p>
                </div>
                <p class="text-xs text-[#2F3A3A]/50 mt-6">Default password: <span class="font-mono">admin123</span> (change in backend/server.py)</p>
            </div>
        </div>

        <div id="admin-dashboard" class="hidden">
            <div class="flex items-center justify-between mb-6">
                <div>
                    <h1 class="text-4xl heading-serif tracking-tighter">Content Manager</h1>
                    <p class="text-[#2F3A3A]/70">Changes are saved instantly and appear on the live site.</p>
                </div>
                <div>
                    <button onclick="saveAllContent()" 
                            class="px-8 h-12 bg-[#2F3A3A] hover:bg-black text-white font-semibold rounded-2xl flex items-center gap-x-2">
                        <i class="fa-solid fa-save"></i>
                        <span>Save All Changes</span>
                    </button>
                </div>
            </div>

            <!-- Quick Stats -->
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                <div class="bg-white border border-[#EDE4DB] rounded-3xl p-5">
                    <div class="text-xs uppercase tracking-widest text-[#A67C6D]">Last Updated</div>
                    <div id="last-updated" class="font-semibold text-xl mt-1">—</div>
                </div>
                <div class="bg-white border border-[#EDE4DB] rounded-3xl p-5">
                    <div class="text-xs uppercase tracking-widest text-[#A67C6D]">Services</div>
                    <div id="stat-services" class="font-semibold text-3xl mt-1">6</div>
                </div>
                <div class="bg-white border border-[#EDE4DB] rounded-3xl p-5">
                    <div class="text-xs uppercase tracking-widest text-[#A67C6D]">Team Members</div>
                    <div id="stat-team" class="font-semibold text-3xl mt-1">4</div>
                </div>
                <div class="bg-white border border-[#EDE4DB] rounded-3xl p-5">
                    <div class="text-xs uppercase tracking-widest text-[#A67C6D]">Gallery Items</div>
                    <div id="stat-gallery" class="font-semibold text-3xl mt-1">8</div>
                </div>
            </div>

            <!-- SETTINGS -->
            <div class="section-card bg-white border border-[#EDE4DB] rounded-3xl p-7 mb-6">
                <h2 class="text-xl font-semibold flex items-center gap-x-2 mb-4">
                    <i class="fa-solid fa-cog text-[#A67C6D]"></i> Site Settings
                </h2>
                <div class="grid md:grid-cols-2 gap-x-6 gap-y-4">
                    <div>
                        <label class="text-xs font-semibold tracking-wider text-[#2F3A3A]/70">PHONE</label>
                        <input id="set-phone" class="form-input w-full border border-[#EDE4DB] rounded-2xl px-4 h-11 mt-1">
                    </div>
                    <div>
                        <label class="text-xs font-semibold tracking-wider text-[#2F3A3A]/70">EMAIL</label>
                        <input id="set-email" class="form-input w-full border border-[#EDE4DB] rounded-2xl px-4 h-11 mt-1">
                    </div>
                    <div class="md:col-span-2">
                        <label class="text-xs font-semibold tracking-wider text-[#2F3A3A]/70">ADDRESS</label>
                        <input id="set-address" class="form-input w-full border border-[#EDE4DB] rounded-2xl px-4 h-11 mt-1">
                    </div>
                </div>
            </div>

            <!-- HERO & ABOUT -->
            <div class="grid md:grid-cols-2 gap-6 mb-6">
                <div class="section-card bg-white border border-[#EDE4DB] rounded-3xl p-7">
                    <h2 class="text-xl font-semibold mb-4">Hero Section</h2>
                    <div class="space-y-4">
                        <div>
                            <label class="text-xs font-semibold tracking-wider">Badge</label>
                            <input id="hero-badge" class="form-input w-full border border-[#EDE4DB] rounded-2xl px-4 h-11 mt-1">
                        </div>
                        <div>
                            <label class="text-xs font-semibold tracking-wider">Headline</label>
                            <input id="hero-headline" class="form-input w-full border border-[#EDE4DB] rounded-2xl px-4 h-11 mt-1">
                        </div>
                        <div>
                            <label class="text-xs font-semibold tracking-wider">Subheadline</label>
                            <textarea id="hero-sub" rows="2" class="form-input w-full border border-[#EDE4DB] rounded-2xl px-4 py-3 mt-1"></textarea>
                        </div>
                    </div>
                </div>

                <div class="section-card bg-white border border-[#EDE4DB] rounded-3xl p-7">
                    <h2 class="text-xl font-semibold mb-4">About Section</h2>
                    <div>
                        <label class="text-xs font-semibold tracking-wider">Headline</label>
                        <input id="about-headline" class="form-input w-full border border-[#EDE4DB] rounded-2xl px-4 h-11 mt-1">
                    </div>
                    <div class="mt-4">
                        <label class="text-xs font-semibold tracking-wider">Paragraph 1</label>
                        <textarea id="about-p1" rows="3" class="form-input w-full border border-[#EDE4DB] rounded-2xl px-4 py-3 mt-1"></textarea>
                    </div>
                </div>
            </div>

            <!-- SERVICES, TEAM, GALLERY, TESTIMONIALS tabs -->
            <div class="bg-white border border-[#EDE4DB] rounded-3xl p-7 mb-8">
                <div class="flex border-b mb-5 overflow-x-auto">
                    <button onclick="showTab('services')" class="tab-btn active px-6 py-3 font-medium" data-tab="services">Services</button>
                    <button onclick="showTab('team')" class="tab-btn px-6 py-3 font-medium" data-tab="team">Team</button>
                    <button onclick="showTab('gallery')" class="tab-btn px-6 py-3 font-medium" data-tab="gallery">Public Gallery</button>
                    <button onclick="showTab('testimonials')" class="tab-btn px-6 py-3 font-medium" data-tab="testimonials">Testimonials</button>
                    <button onclick="showTab('media')" class="tab-btn px-6 py-3 font-medium text-[#A67C6D]" data-tab="media">
                        <i class="fa-solid fa-photo-video mr-1"></i> Media Library
                    </button>
                    <button onclick="showTab('bookings')" class="tab-btn px-6 py-3 font-medium" data-tab="bookings">
                        <i class="fa-solid fa-credit-card mr-1"></i> Bookings
                    </button>
                </div>

                <div id="tab-services">
                    <div class="flex justify-between items-center mb-4">
                        <h3 class="font-semibold">Services</h3>
                        <button onclick="addNewService()" class="text-sm px-4 py-2 bg-[#A67C6D] text-white rounded-2xl">+ Add Service</button>
                    </div>
                    <div id="services-list" class="space-y-3"></div>
                </div>

                <div id="tab-team" class="hidden">
                    <div class="flex justify-between items-center mb-4">
                        <h3 class="font-semibold">Team Members</h3>
                    </div>
                    <div id="team-list" class="space-y-3"></div>
                </div>

                <div id="tab-gallery" class="hidden">
                    <div class="flex justify-between items-center mb-4">
                        <h3 class="font-semibold">Public Gallery (shown on website)</h3>
                        <button onclick="uploadMediaForGallery()" class="text-sm px-4 py-2 bg-[#A67C6D] text-white rounded-2xl">Upload New Media</button>
                    </div>
                    <div id="gallery-list" class="grid grid-cols-2 md:grid-cols-4 gap-3"></div>
                </div>

                <div id="tab-testimonials" class="hidden">
                    <div class="flex justify-between items-center mb-4">
                        <h3 class="font-semibold">Testimonials</h3>
                    </div>
                    <div id="testimonials-list" class="space-y-3"></div>
                </div>

                <!-- MEDIA LIBRARY TAB -->
                <div id="tab-media" class="hidden">
                    <div class="flex justify-between items-center mb-4">
                        <h3 class="font-semibold">Media Library (your asset pool)</h3>
                        <div class="flex gap-2">
                            <button onclick="rescanMedia()" 
                                    class="text-sm px-4 py-2 bg-white border border-[#EDE4DB] hover:bg-[#EDE4DB] rounded-2xl flex items-center gap-x-2">
                                <i class="fa-solid fa-sync"></i>
                                <span>Rescan from Disk</span>
                            </button>
                            <button onclick="uploadNewMediaGlobal()" 
                                    class="text-sm px-4 py-2 bg-[#A67C6D] hover:bg-[#8F685C] text-white rounded-2xl flex items-center gap-x-2">
                                <i class="fa-solid fa-upload"></i>
                                <span>Upload New Media</span>
                            </button>
                        </div>
                    </div>
                    <div id="media-library-grid" class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4"></div>
                    <p class="text-xs text-[#2F3A3A]/60 mt-4">Central asset pool. All files in <code>backend/uploads/</code> appear here automatically. Use this to assign images/videos to Hero, Team, Services, etc. The separate "Public Gallery" tab controls what visitors see on the live site.</p>
                </div>

                <!-- BOOKINGS TAB (Stripe) -->
                <div id="tab-bookings" class="hidden">
                    <div class="flex justify-between items-center mb-4">
                        <h3 class="font-semibold">Recent Paid Bookings</h3>
                        <button onclick="loadBookings()" 
                                class="text-sm px-4 py-2 bg-white border border-[#EDE4DB] hover:bg-[#EDE4DB] rounded-2xl flex items-center gap-x-2">
                            <i class="fa-solid fa-sync"></i>
                            <span>Refresh</span>
                        </button>
                    </div>
                    <div id="bookings-list" class="space-y-3 text-sm"></div>
                    <p class="text-xs text-[#2F3A3A]/60 mt-4">Bookings appear here automatically after successful Stripe payments (via webhook or success redirect). Works best when STRIPE_WEBHOOK_SECRET is configured.</p>
                </div>
            </div>

            <div class="text-center text-xs text-[#2F3A3A]/50">
                Changes are saved to <code>backend/data/content.json</code>. The live site will pick them up when refreshed (or when backend is running).
            </div>
        </div>
    </div>

    <script>
        const API = "http://localhost:5050/api";
        let currentContent = null;

        function viewSite() {
            // Smart "View Site" button:
            // - When developing locally: opens the static site (run with: python3 -m http.server 8000)
            // - Falls back to the published GitHub Pages demo
            const localStatic = 'http://localhost:8000';
            const liveDemo = 'https://lionelsinaisinelnikoff.github.io/pawfect-grooming';

            // Always try local first (most common when using the admin)
            window.open(localStatic, '_blank');
        }

        async function checkAuth() {
            try {
                const res = await fetch(`${API}/auth/status`, { credentials: 'include' });
                const data = await res.json();
                if (data.loggedIn) {
                    document.getElementById('login-screen').classList.add('hidden');
                    document.getElementById('admin-dashboard').classList.remove('hidden');
                    await loadContent();
                } else {
                    document.getElementById('login-screen').classList.remove('hidden');
                    document.getElementById('admin-dashboard').classList.add('hidden');
                }
            } catch (e) {
                // Backend not running
                document.getElementById('login-screen').classList.remove('hidden');
            }
        }

        async function performLogin() {
            const pw = document.getElementById('password-input').value;
            const errorEl = document.getElementById('login-error');
            errorEl.classList.add('hidden');

            try {
                const res = await fetch(`${API}/login`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({ password: pw })
                });
                const data = await res.json();
                if (data.success) {
                    await checkAuth();
                } else {
                    errorEl.textContent = data.error || "Login failed";
                    errorEl.classList.remove('hidden');
                }
            } catch (e) {
                errorEl.textContent = "Cannot connect to backend. Is the server running?";
                errorEl.classList.remove('hidden');
            }
        }

        async function logout() {
            await fetch(`${API}/logout`, { method: 'POST', credentials: 'include' });
            location.reload();
        }

        async function loadContent() {
            const res = await fetch(`${API}/content`, { credentials: 'include' });
            currentContent = await res.json();

            // Load media library in parallel
            await loadMediaLibrary();

            // Populate form fields
            document.getElementById('set-phone').value = currentContent.settings.phone || '';
            document.getElementById('set-email').value = currentContent.settings.email || '';
            document.getElementById('set-address').value = currentContent.settings.address || '';

            document.getElementById('hero-badge').value = currentContent.hero.badge || '';
            document.getElementById('hero-headline').value = currentContent.hero.headline || '';
            document.getElementById('hero-sub').value = (currentContent.hero.subheadline || '').replace(/<br>/g, '\\n');

            document.getElementById('about-headline').value = currentContent.about.headline || '';
            document.getElementById('about-p1').value = currentContent.about.paragraph1 || '';

            document.getElementById('last-updated').textContent = new Date(currentContent.meta.lastUpdated).toLocaleString();

            renderServices();
            renderTeam();
            renderGallery();
            renderTestimonials();

            // Update stats
            document.getElementById('stat-services').textContent = currentContent.services.length;
            document.getElementById('stat-team').textContent = currentContent.team.length;
            document.getElementById('stat-gallery').textContent = currentContent.gallery.length;

            // Preload media library grid in background (so tab feels instant)
            setTimeout(() => {
                const mediaTab = document.getElementById('tab-media');
                if (mediaTab && !mediaTab.classList.contains('hidden')) {
                    renderMediaLibrary();
                }
            }, 300);
        }

        function renderServices() {
            const container = document.getElementById('services-list');
            container.innerHTML = '';

            currentContent.services.forEach((svc, idx) => {
                const mediaId = svc.imageMediaId;
                const media = mediaId ? currentMediaLibrary[mediaId] : null;
                const mediaUrl = media ? media.url : 'https://placehold.co/96x72?text=No+Image';
                const isVideo = media && media.type === 'video';

                const div = document.createElement('div');
                div.className = 'border border-[#EDE4DB] rounded-2xl p-4 flex gap-4 items-start';
                div.innerHTML = `
                    <div class="w-28 flex-shrink-0">
                        ${isVideo 
                            ? `<video src="${mediaUrl}" poster="${media.poster || ''}" class="w-24 h-20 object-cover rounded-xl border border-[#EDE4DB]" muted loop playsinline></video>` 
                            : `<img src="${mediaUrl}" class="w-24 h-20 object-cover rounded-xl border border-[#EDE4DB]">`
                        }
                        <button class="mt-2 text-xs w-full py-1 bg-[#A67C6D] text-white rounded-xl hover:bg-[#8F685C]" 
                                data-action="change-service-image" data-index="${idx}">
                            Change Media
                        </button>
                    </div>
                    <div class="flex-1 min-w-0">
                        <div class="grid grid-cols-1 md:grid-cols-5 gap-3">
                            <input value="${svc.name}" onchange="updateService(${idx}, 'name', this.value)" class="border border-[#EDE4DB] rounded-xl px-3 h-10 text-sm">
                            <input value="${svc.priceLabel}" onchange="updateService(${idx}, 'priceLabel', this.value)" class="border border-[#EDE4DB] rounded-xl px-3 h-10 text-sm">
                            <input value="${svc.duration}" onchange="updateService(${idx}, 'duration', this.value)" class="border border-[#EDE4DB] rounded-xl px-3 h-10 text-sm">
                            <input value="${svc.icon}" onchange="updateService(${idx}, 'icon', this.value)" class="border border-[#EDE4DB] rounded-xl px-3 h-10 text-sm">
                            <div class="md:col-span-5">
                                <textarea onchange="updateService(${idx}, 'description', this.value)" class="border border-[#EDE4DB] rounded-xl px-3 py-2 text-sm w-full h-16">${svc.description}</textarea>
                            </div>
                        </div>
                    </div>
                    <button onclick="deleteService(${idx})" class="text-red-500 px-3 self-start"><i class="fa-solid fa-trash"></i></button>
                `;
                container.appendChild(div);

                // Wire change image button
                const btn = div.querySelector('[data-action="change-service-image"]');
                if (btn) {
                    btn.onclick = () => {
                        showMediaPicker((selectedMedia) => {
                            currentContent.services[idx].imageMediaId = selectedMedia.id;
                            renderServices();
                        });
                    };
                }
            });
        }

        function updateService(idx, field, value) {
            currentContent.services[idx][field] = value;
        }

        function addNewService() {
            currentContent.services.push({
                id: Date.now(),
                name: "New Service",
                priceLabel: "$XX",
                duration: "30 min",
                description: "Description here...",
                icon: "spa",
                imageMediaId: null,
                active: true
            });
            renderServices();
        }

        function deleteService(idx) {
            if (confirm("Delete this service?")) {
                currentContent.services.splice(idx, 1);
                renderServices();
            }
        }

        // Simplified renders for team, gallery, testimonials (for brevity in MVP)
        function renderTeam() {
            const c = document.getElementById('team-list');
            c.innerHTML = '';

            currentContent.team.forEach((t, i) => {
                const mediaId = t.photoMediaId;
                const media = mediaId ? currentMediaLibrary[mediaId] : null;
                const photoUrl = media ? media.url : (t.photo ? '../' + t.photo : 'https://placehold.co/80x80?text=No+Photo');

                const div = document.createElement('div');
                div.className = 'border border-[#EDE4DB] rounded-2xl p-4 flex gap-4 items-start';
                div.innerHTML = `
                    <div class="w-24 flex-shrink-0">
                        <img src="${photoUrl}" class="w-20 h-20 object-cover rounded-2xl border border-[#EDE4DB]">
                        <button class="mt-2 text-xs w-full py-1 bg-[#A67C6D] text-white rounded-xl hover:bg-[#8F685C]" 
                                data-action="change-photo" data-index="${i}">
                            Change Photo
                        </button>
                    </div>
                    <div class="flex-1 min-w-0">
                        <input value="${t.name}" class="font-semibold w-full border-b pb-1 mb-1 text-lg" onchange="currentContent.team[${i}].name = this.value">
                        <input value="${t.title}" class="text-sm text-[#A67C6D] w-full" onchange="currentContent.team[${i}].title = this.value">
                        <textarea class="text-sm w-full mt-2 border border-[#EDE4DB] rounded p-2 h-20" onchange="currentContent.team[${i}].bio = this.value">${t.bio}</textarea>
                        <div class="flex gap-2 mt-2 text-xs">
                            <span class="bg-[#EDE4DB] px-2 py-0.5 rounded">${t.years} yrs</span>
                            <input value="${t.years}" class="w-12 border rounded px-1" onchange="currentContent.team[${i}].years = this.value">
                        </div>
                    </div>
                `;
                c.appendChild(div);

                // Wire the change photo button
                const btn = div.querySelector('[data-action="change-photo"]');
                btn.onclick = async () => {
                    showMediaPicker((selectedMedia) => {
                        currentContent.team[i].photoMediaId = selectedMedia.id;
                        // Keep legacy photo field for backward compatibility if needed
                        currentContent.team[i].photo = selectedMedia.url.replace('/media/', '');
                        renderTeam();
                    });
                };
            });
        }

        function renderGallery() {
            const c = document.getElementById('gallery-list');
            c.innerHTML = '';

            currentContent.gallery.forEach((g, i) => {
                const related = g.relatedTo || { type: 'showcase', label: 'Showcase' };
                let relatedLabel = related.label || related.type;

                if (related.type === 'team' && related.id) {
                    const member = currentContent.team.find(m => m.id == related.id);
                    if (member) relatedLabel = `${member.name} (Team)`;
                }
                if (related.type === 'service' && related.id) {
                    const svc = currentContent.services.find(s => s.id == related.id);
                    if (svc) relatedLabel = `${svc.name} (Service)`;
                }

                const media = g.mediaId ? currentMediaLibrary[g.mediaId] : null;
                const mediaUrl = media ? media.url : (g.src ? (g.src.startsWith('/') ? g.src : '../' + g.src) : '');

                const thumb = g.mediaType === 'video'
                    ? `<video src="${mediaUrl}" poster="${g.poster ? '../' + g.poster : (media ? media.poster : '')}" class="w-full aspect-video object-cover bg-black" muted></video>`
                    : `<img src="${mediaUrl}" class="w-full aspect-video object-cover">`;

                const div = document.createElement('div');
                div.className = 'media-item border border-[#EDE4DB] rounded-2xl overflow-hidden bg-white text-xs';
                div.innerHTML = `
                    ${thumb}
                    <div class="p-2.5">
                        <div class="font-medium truncate">${g.caption}</div>
                        <div class="text-[#A67C6D] mt-0.5">${relatedLabel}</div>
                        <div class="text-[10px] text-[#2F3A3A]/50 mt-1">${g.type} • ${g.mediaType}</div>
                    </div>
                `;
                c.appendChild(div);
            });
        }

        function renderTestimonials() {
            const c = document.getElementById('testimonials-list');
            c.innerHTML = currentContent.testimonials.map((t, i) => `
                <div class="border border-[#EDE4DB] rounded-2xl p-4">
                    <textarea class="w-full text-sm border border-[#EDE4DB] rounded p-2" onchange="currentContent.testimonials[${i}].quote = this.value">${t.quote}</textarea>
                    <div class="flex gap-2 mt-2">
                        <input value="${t.author}" class="flex-1 text-sm border border-[#EDE4DB] rounded px-2" onchange="currentContent.testimonials[${i}].author = this.value">
                        <input value="${t.petInfo}" class="flex-1 text-sm border border-[#EDE4DB] rounded px-2" onchange="currentContent.testimonials[${i}].petInfo = this.value">
                    </div>
                </div>
            `).join('');
        }

        async function loadBookings() {
            const container = document.getElementById('bookings-list');
            container.innerHTML = '<div class="text-[#A67C6D] py-4">Loading bookings from backend...</div>';

            try {
                const res = await fetch(`${API}/bookings`, { credentials: 'include' });
                const bookings = await res.json();

                if (!bookings || bookings.length === 0) {
                    container.innerHTML = `
                        <div class="border border-[#EDE4DB] rounded-2xl p-8 text-center bg-white">
                            <i class="fa-solid fa-credit-card text-3xl text-[#A67C6D]/40 mb-3"></i>
                            <div class="font-medium">No paid bookings yet</div>
                            <div class="text-xs text-[#2F3A3A]/60 mt-1">Successful Stripe payments will appear here automatically.</div>
                        </div>`;
                    return;
                }

                container.innerHTML = bookings.map(b => {
                    const amount = b.amountTotal ? (b.amountTotal / 100).toFixed(2) : '—';
                    const date = b.preferredDate || '—';
                    const time = b.preferredTime || '';
                    return `
                        <div class="border border-[#EDE4DB] rounded-2xl p-4 bg-white">
                            <div class="flex justify-between items-start">
                                <div>
                                    <div class="font-semibold">${b.petName || 'Pet'} — ${b.service || 'Service'}</div>
                                    <div class="text-[#A67C6D] text-xs mt-0.5">${b.ownerName || ''} • ${b.customerEmail || ''}</div>
                                </div>
                                <div class="text-right">
                                    <div class="font-semibold text-[#A67C6D]">$${amount}</div>
                                    <div class="text-[10px] text-[#2F3A3A]/50">${date} ${time}</div>
                                </div>
                            </div>
                            ${b.notes ? `<div class="mt-2 text-xs bg-[#FDF8F4] p-2 rounded-xl text-[#2F3A3A]/70">${b.notes}</div>` : ''}
                            <div class="mt-2 text-[10px] text-[#2F3A3A]/40">Status: <span class="font-medium text-emerald-600">${b.status || 'paid'}</span> • ${b.createdAt ? new Date(b.createdAt).toLocaleString() : ''}</div>
                        </div>
                    `;
                }).join('');
            } catch (e) {
                container.innerHTML = `<div class="text-red-600 text-sm">Could not load bookings. Is the backend running?</div>`;
            }
        }

        function showTab(tab) {
            document.querySelectorAll('[id^="tab-"]').forEach(el => el.classList.add('hidden'));
            document.getElementById('tab-' + tab).classList.remove('hidden');
            
            document.querySelectorAll('.tab-btn').forEach(btn => {
                const isActive = btn.dataset.tab === tab;
                btn.classList.toggle('active', isActive);
                btn.classList.toggle('border-b-2', isActive);
                btn.classList.toggle('border-[#A67C6D]', isActive);
            });

            if (tab === 'media') {
                renderMediaLibrary();
            }
            if (tab === 'bookings') {
                loadBookings();
            }
        }

        async function saveAllContent() {
            // Collect simple fields
            currentContent.settings.phone = document.getElementById('set-phone').value;
            currentContent.settings.email = document.getElementById('set-email').value;
            currentContent.settings.address = document.getElementById('set-address').value;

            currentContent.hero.badge = document.getElementById('hero-badge').value;
            currentContent.hero.headline = document.getElementById('hero-headline').value;
            currentContent.hero.subheadline = document.getElementById('hero-sub').value.replace(/\\n/g, '<br>');

            currentContent.about.headline = document.getElementById('about-headline').value;
            currentContent.about.paragraph1 = document.getElementById('about-p1').value;

            const res = await fetch(`${API}/content?merge=true`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(currentContent)
            });
            const result = await res.json();
            if (result.success) {
                alert("Content saved successfully! Refresh the public site to see changes.");
                await loadContent();
            } else {
                alert("Error saving: " + (result.error || "Unknown"));
            }
        }

        async function uploadMediaForGallery() {
            const input = document.createElement('input');
            input.type = 'file';
            input.accept = 'image/*,video/*';
            input.onchange = async (e) => {
                const file = e.target.files[0];
                if (!file) return;

                const form = new FormData();
                form.append('file', file);

                const res = await fetch(`${API}/upload`, {
                    method: 'POST',
                    credentials: 'include',
                    body: form
                });
                const data = await res.json();
                if (data.success) {
                    currentContent.gallery.push({
                        id: Date.now(),
                        mediaId: data.mediaId,
                        src: data.url,
                        alt: file.name,
                        caption: file.name.split('.')[0],
                        type: 'dog',
                        mediaType: data.type,
                        poster: data.type === 'video' ? 'images/happy-group.jpg' : '',
                        relatedTo: { type: "showcase", label: "Client Showcase" }
                    });
                    renderGallery();
                    alert("Media uploaded and added to gallery. Save All Changes when done.");
                }
            };
            input.click();
        }

        // ==================== NEW MEDIA LIBRARY + PICKER ====================

        let currentMediaLibrary = {};

        async function loadMediaLibrary() {
            const res = await fetch(`${API}/media`, { credentials: 'include' });
            const data = await res.json();
            currentMediaLibrary = {};
            data.forEach(item => {
                currentMediaLibrary[item.id] = item;
            });
            return data;
        }

        async function renderMediaLibrary() {
            const container = document.getElementById('media-library-grid');
            container.innerHTML = '<div class="col-span-full text-center py-8 text-[#2F3A3A]/50">Scanning backend/uploads/ ...</div>';

            const mediaItems = await loadMediaLibrary();
            container.innerHTML = '';

            // Show count
            const countDiv = document.createElement('div');
            countDiv.className = 'col-span-full text-xs text-[#A67C6D] mb-2 pl-1';
            countDiv.textContent = `Found ${mediaItems.length} file(s) in backend/uploads/`;
            container.appendChild(countDiv);

            if (mediaItems.length === 0) {
                const empty = document.createElement('div');
                empty.className = 'col-span-full text-center py-8 text-[#2F3A3A]/60';
                empty.textContent = 'No media files found in backend/uploads/. Upload some using the button above.';
                container.appendChild(empty);
                return;
            }

            mediaItems.forEach(item => {
                const usageHtml = item.usage && item.usage.length > 0 
                    ? item.usage.map(u => `<span class="text-[10px] bg-[#EDE4DB] px-1.5 py-px rounded">${u.label}</span>`).join(' ')
                    : '<span class="text-[10px] text-[#A67C6D]/70">Not assigned</span>';

                const div = document.createElement('div');
                div.className = 'border border-[#EDE4DB] rounded-2xl overflow-hidden bg-white cursor-pointer media-item';
                
                let mediaHtml = '';
                if (item.type === 'video') {
                    mediaHtml = `
                        <video src="${item.url}" poster="${item.poster || ''}" 
                               class="w-full h-28 object-cover bg-black" muted 
                               onerror="this.style.display='none'; this.parentNode.insertAdjacentHTML('afterbegin', '<div class=\\'w-full h-28 bg-[#2F3A3A] flex items-center justify-center text-white/60 text-xs\\'>Video unavailable</div>')">
                        </video>`;
                } else {
                    mediaHtml = `
                        <img src="${item.url}" class="w-full h-28 object-cover" 
                             onerror="this.src='data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 width=%27100%27 height=%27100%27%3E%3Crect fill=%27%23EDE4DB%27 width=%27100%27 height=%27100%27/%3E%3Ctext x=%2750%25%27 y=%2750%25%27 dominant-baseline=%27middle%27 text-anchor=%27middle%27 fill=%27%23A67C6D%27 font-size=%2712%27%3EImage%3C/text%3E%3C/svg%3E'">`;
                }

                div.innerHTML = `
                    <div class="relative">
                        ${mediaHtml}
                        <div class="absolute top-1 right-1 text-[9px] px-1.5 py-0.5 bg-black/70 text-white rounded">${item.type}</div>
                    </div>
                    <div class="p-2 text-xs">
                        <div class="font-medium truncate">${item.originalName || item.filename}</div>
                        <div class="mt-1 flex flex-wrap gap-1">${usageHtml}</div>
                    </div>
                `;
                div.onclick = () => showMediaDetails(item);
                container.appendChild(div);
            });
        }

        function showMediaDetails(mediaItem) {
            const usageText = mediaItem.usage && mediaItem.usage.length > 0
                ? mediaItem.usage.map(u => u.label).join(', ')
                : 'Not currently assigned to any element.';

            const modal = document.createElement('div');
            modal.className = 'fixed inset-0 z-[110] bg-black/70 flex items-center justify-center p-6';
            modal.innerHTML = `
                <div class="bg-white rounded-3xl max-w-lg w-full overflow-hidden shadow-2xl">
                    <div class="p-6">
                        <div class="flex justify-between items-start">
                            <div>
                                <div class="font-semibold text-lg">${mediaItem.originalName || mediaItem.filename}</div>
                                <div class="text-xs text-[#A67C6D]">${mediaItem.type.toUpperCase()} • ${mediaItem.filename}</div>
                            </div>
                            <button onclick="this.closest('.fixed').remove()" class="text-2xl leading-none text-[#2F3A3A]/40">×</button>
                        </div>

                        <div class="my-4">
                            ${mediaItem.type === 'video' 
                                ? `<video controls class="w-full rounded-2xl" src="${mediaItem.url}" poster="${mediaItem.poster || ''}"></video>`
                                : `<img src="${mediaItem.url}" class="w-full rounded-2xl">`}
                        </div>

                        <div class="text-sm">
                            <div class="font-semibold mb-1">Currently used in:</div>
                            <div class="text-[#2F3A3A]/80">${usageText}</div>
                        </div>
                    </div>

                    <div class="bg-[#FDF8F4] p-6 flex flex-wrap gap-3">
                        <button onclick="assignMediaToContext('${mediaItem.id}', this)" 
                                class="flex-1 min-w-[140px] px-4 py-2.5 bg-[#2F3A3A] text-white rounded-2xl text-sm font-semibold">
                            Assign to Element...
                        </button>
                        <button onclick="this.closest('.fixed').remove()" 
                                class="px-6 py-2.5 border border-[#EDE4DB] rounded-2xl text-sm font-medium">
                            Close
                        </button>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }

        async function assignMediaToContext(mediaId, btnElement) {
            const type = prompt("Assign to which type? (hero / about / team / service / gallery)", "team");
            if (!type) return;

            let targetId = null;
            if (['team', 'service', 'gallery'].includes(type)) {
                targetId = prompt(`Enter the ID of the ${type} item (e.g. 1 for Sarah Kline):`);
                if (!targetId) return;
            }

            const res = await fetch(`${API}/media/assign`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({
                    mediaId: mediaId,
                    elementType: type,
                    elementId: targetId
                })
            });

            const data = await res.json();
            if (data.success) {
                alert("Media assigned successfully! Saving content...");
                await saveAllContent();
                btnElement.closest('.fixed').remove();
                await renderMediaLibrary();
                // Refresh current tab
                if (document.getElementById('tab-team').classList.contains('hidden') === false) renderTeam();
                if (document.getElementById('tab-services').classList.contains('hidden') === false) renderServices();
                if (document.getElementById('tab-gallery').classList.contains('hidden') === false) renderGallery();
            } else {
                alert("Assignment failed: " + (data.error || "Unknown error"));
            }
        }

        async function uploadNewMediaGlobal() {
            const input = document.createElement('input');
            input.type = 'file';
            input.accept = 'image/*,video/*';
            input.onchange = async (e) => {
                const file = e.target.files[0];
                if (!file) return;

                const form = new FormData();
                form.append('file', file);

                const res = await fetch(`${API}/upload`, {
                    method: 'POST',
                    credentials: 'include',
                    body: form
                });
                const data = await res.json();
                if (data.success) {
                    alert(`Uploaded! Media ID: ${data.mediaId}`);
                    await renderMediaLibrary();
                }
            };
            input.click();
        }

        async function rescanMedia() {
            const container = document.getElementById('media-library-grid');
            container.innerHTML = '<div class="col-span-full text-center py-8 text-[#2F3A3A]/50">Scanning backend/uploads/ folder...</div>';
            await renderMediaLibrary();
        }

        // Simple media picker (can be expanded)
        async function showMediaPicker(onSelect) {
            const mediaItems = await loadMediaLibrary();
            const picker = document.createElement('div');
            picker.className = 'fixed inset-0 z-[120] bg-black/70 flex items-center justify-center p-6';
            picker.innerHTML = `
                <div class="bg-white rounded-3xl w-full max-w-4xl max-h-[80vh] overflow-auto p-6">
                    <div class="flex justify-between mb-4">
                        <h3 class="font-semibold text-xl">Choose Media</h3>
                        <button onclick="this.closest('.fixed').remove()" class="text-xl">×</button>
                    </div>
                    <div class="grid grid-cols-2 md:grid-cols-5 gap-3" id="picker-grid"></div>
                </div>
            `;
            document.body.appendChild(picker);

            const grid = picker.querySelector('#picker-grid');
            Object.values(mediaItems).forEach(item => {
                const el = document.createElement('div');
                el.className = 'cursor-pointer border rounded-2xl overflow-hidden';
                el.innerHTML = item.type === 'video' 
                    ? `<video src="${item.url}" poster="${item.poster || ''}" class="w-full h-24 object-cover" muted></video>`
                    : `<img src="${item.url}" class="w-full h-24 object-cover">`;
                el.onclick = () => {
                    picker.remove();
                    onSelect(item);
                };
                grid.appendChild(el);
            });
        }

        function updateStatsFromContent() {
            // called after load
        }

        // Init
        window.onload = () => {
            checkAuth();
            
            // Make inputs save on blur for convenience
            document.querySelectorAll('input, textarea').forEach(el => {
                el.addEventListener('blur', () => {
                    // Could auto-save here in future
                });
            });
        };
    </script>
</body>
</html>
"""

@app.route("/admin")
def admin_page():
    if not session.get("logged_in"):
        # Show login screen inside the same beautiful page
        return render_template_string(ADMIN_HTML)
    return render_template_string(ADMIN_HTML)


# ---------------- MAIN ----------------
if __name__ == "__main__":
    print("🐾 Pawfect Grooming Content Backend")
    print("-----------------------------------")
    print(f"Admin password: {DEFAULT_ADMIN_PASSWORD}")
    stripe_status = "ENABLED ✓" if (stripe and STRIPE_SECRET_KEY) else "DISABLED (set STRIPE_SECRET_KEY)"
    print(f"Stripe payments: {stripe_status}")
    print("Visit: http://localhost:5050/admin")
    print("Press CTRL+C to stop\n")
    app.run(host="0.0.0.0", port=5050, debug=True)