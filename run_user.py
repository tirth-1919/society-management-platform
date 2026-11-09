"""
Society Management SaaS Platform – User Portal Entry Point
Run with: python run_user.py
URL: http://127.0.0.1:5000
"""

import os
import sys

from dotenv import load_dotenv
from app import create_app
from app.models import db

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()
os.environ["SESSION_COOKIE_NAME"] = "society_user_session"

app = create_app()
app.config["SESSION_COOKIE_NAME"] = "society_user_session"

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        from app.models.tenant import patch_sqlite_schema

        patch_sqlite_schema()
        print("[OK] User Portal: Database tables created/verified.")

    port = int(os.environ.get("USER_PORT", 5000))
    debug = os.environ.get("FLASK_ENV", "development") == "development"
    print(f"[RUNNING] User Portal running on http://127.0.0.1:{port}")
    # Bind all local interfaces so an ngrok tunnel can forward to this portal.
    app.run(host="0.0.0.0", port=port, debug=debug) 
