"""
Society Management SaaS Platform – Admin Portal Entry Point
Run with: python run_admin.py
URL: http://127.0.0.1:5001/admin/login
"""

import os
import sys
from dotenv import load_dotenv
from flask import redirect
sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()
# Set the Admin cookie name before importing/creating the Flask app so the
# Admin service is initialized with its own session from the first request.
os.environ["SESSION_COOKIE_NAME"] = "society_admin_session"

from app import create_app  # noqa: E402
app = create_app()
app.config["SESSION_COOKIE_NAME"] = "society_admin_session"


# ── Override the root '/' to redirect to Admin Login ──────────────────────
# main_bp already registered '/' as index(), so we override it via view_functions.
def admin_portal_root():
    return redirect("/admin/login", code=302)


# Replace the registered view function for the root URL
app.view_functions["main.index"] = admin_portal_root

if __name__ == "__main__":
    port = int(os.environ.get("ADMIN_PORT", 5001))
    debug = os.environ.get("FLASK_ENV", "development") == "development"
    print(f"[RUNNING] Admin Portal running on http://127.0.0.1:{port}/admin/login")
    # Bind all local interfaces so an ngrok tunnel can forward to this portal.
    app.run(host="0.0.0.0", port=port, debug=debug)
