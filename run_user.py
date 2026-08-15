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

        # Seed demo data if societies table is empty
        from app.models import Society, Building, Flat, User, Role

        if Society.query.count() == 0:
            print("[SEEDING] Creating demo society data...")
            s1 = Society(
                name="Green Valley Society",
                registration_number="GVS-001",
                address="123 Park Avenue",
                city="Mumbai",
                state="Maharashtra",
                pincode="400001",
                phone="9000000001",
                email="gvs@society.com",
            )
            s2 = Society(
                name="Sunrise Apartments",
                registration_number="SRA-002",
                address="456 Hill Road",
                city="Pune",
                state="Maharashtra",
                pincode="411001",
                phone="9000000002",
                email="sunrise@society.com",
            )
            db.session.add_all([s1, s2])
            db.session.commit()

            b1 = Building(
                society_id=s1.id, name="Wing A", floors_count=6, total_flats=24
            )
            b2 = Building(
                society_id=s1.id, name="Wing B", floors_count=6, total_flats=24
            )
            b3 = Building(
                society_id=s2.id, name="Tower 1", floors_count=8, total_flats=32
            )
            db.session.add_all([b1, b2, b3])
            db.session.commit()

            from app.models import Block

            blk1 = Block(society_id=s1.id, building_id=b1.id, name="Block 1")
            blk2 = Block(society_id=s1.id, building_id=b1.id, name="Block 2")
            blk3 = Block(society_id=s1.id, building_id=b2.id, name="Block A")
            blk4 = Block(society_id=s2.id, building_id=b3.id, name="Block East")
            db.session.add_all([blk1, blk2, blk3, blk4])
            db.session.commit()

            flats = []
            for floor in range(1, 7):
                for unit in range(1, 5):
                    blk = blk1 if unit <= 2 else blk2
                    flats.append(
                        Flat(
                            society_id=s1.id,
                            building_id=b1.id,
                            block_id=blk.id,
                            flat_number=f"A-{floor}0{unit}",
                            floor_number=floor,
                            flat_type="2BHK",
                        )
                    )
                    flats.append(
                        Flat(
                            society_id=s1.id,
                            building_id=b2.id,
                            block_id=blk3.id,
                            flat_number=f"B-{floor}0{unit}",
                            floor_number=floor,
                            flat_type="3BHK",
                        )
                    )
            for floor in range(1, 5):
                for unit in range(1, 5):
                    flats.append(
                        Flat(
                            society_id=s2.id,
                            building_id=b3.id,
                            block_id=blk4.id,
                            flat_number=f"T1-{floor}0{unit}",
                            floor_number=floor,
                            flat_type="2BHK",
                        )
                    )
            db.session.add_all(flats)
            db.session.commit()
            print(
                f"[SEEDED] {len(flats)} flats created across 4 blocks and 3 buildings in 2 societies"
            )

        # Seed Super Admin if not exists
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
            print("[SEEDED] Super Admin: admin / Admin@123")

    port = int(os.environ.get("USER_PORT", 5000))
    debug = os.environ.get("FLASK_ENV", "development") == "development"
    print(f"[RUNNING] User Portal running on http://127.0.0.1:{port}")
    # Bind all local interfaces so an ngrok tunnel can forward to this portal.
    app.run(host="0.0.0.0", port=port, debug=debug)
