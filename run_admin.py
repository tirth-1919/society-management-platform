"""
Society Management SaaS Platform – Admin Portal Entry Point
Run with: python run_admin.py
URL: http://127.0.0.1:5001/admin/login
"""

import os
import sys

from dotenv import load_dotenv
from flask import redirect
from app import create_app
from app.models import db

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()
os.environ["SESSION_COOKIE_NAME"] = "society_admin_session"

app = create_app()
app.config["SESSION_COOKIE_NAME"] = "society_admin_session"


# ── Override the root '/' to redirect to Admin Login ──────────────────────
# main_bp already registered '/' as index(), so we override it via view_functions.
def admin_portal_root():
    return redirect("/admin/login", code=302)


# Replace the registered view function for the root URL
app.view_functions["main.index"] = admin_portal_root

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        from app.models.tenant import patch_sqlite_schema

        patch_sqlite_schema()
        print("[OK] Admin Portal: Database tables created/verified.")

        from app.models import User, Role

        admin = User.query.filter_by(username="admin").first()
        if not admin:
            admin = User(
                username="admin",
                full_name="Super Admin",
                mobile="9000000000",
                email="admin@society.com",
                role=Role.SUPER_ADMIN,
                account_status="ACTIVE",
                is_active=True,
            )
            admin.set_password("Admin@123")
            db.session.add(admin)
            db.session.commit()
            print("[SEEDED] Super Admin created: admin / Admin@123")
        else:
            print(f"[OK] Super Admin exists: username={admin.username}")

    port = int(os.environ.get("ADMIN_PORT", 5001))
    debug = os.environ.get("FLASK_ENV", "development") == "development"
    print(f"[RUNNING] Admin Portal running on http://127.0.0.1:{port}/admin/login")
    # Bind all local interfaces so an ngrok tunnel can forward to this portal.
    app.run(host="0.0.0.0", port=port, debug=debug)
