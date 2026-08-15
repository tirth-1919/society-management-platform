"""
Society Management SaaS Platform - Application Entry Point
Run with: python run.py
"""

import os

from app import create_app
from app.models import db

app = create_app()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        print("[OK] Database tables created/verified.")

    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV", "development") == "development"

    print(f"[OK] Society SaaS Platform running on http://127.0.0.1:{port}")

    app.run(
        host="0.0.0.0",
        port=port,
        debug=debug,
    )


