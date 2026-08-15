"""Society Management SaaS - Database Seeder
Run with: python seed.py
"""

from datetime import date, timedelta
import sys

from dotenv import load_dotenv

from app import create_app
from app.models import db
from app.models.tenant import Society, Building, Flat
from app.models.user import User, Role
from app.models.resident import Resident
from app.models.billing import MaintenanceConfig, MaintenanceBill
from app.models.complaint import ComplaintCategory, Complaint
from app.models.facility import Facility
from app.models.operations import Staff
from app.models.communication import Notice
from app.utils import utcnow


sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

app = create_app()

with app.app_context():
    db.create_all()
    print("[OK] Database tables created/verified.")

    # --------------------------------------------------
    # SUPER ADMIN
    # --------------------------------------------------
    admin_user = User.query.filter(
        (User.username == "admin") | (User.mobile == "9000000000")
    ).first()

    if not admin_user:
        admin_user = User(
            username="admin",
            full_name="Super Admin",
            mobile="9000000000",
            email="admin@societysaas.in",
            role=Role.SUPER_ADMIN,
            society_id=None,
            account_status="ACTIVE",
            is_active=True,
        )
        admin_user.set_password("Admin@123")
        db.session.add(admin_user)
        db.session.commit()
        print("[OK] Super Admin created.")
    else:
        admin_user.username = "admin"
        admin_user.account_status = "ACTIVE"
        admin_user.is_active = True
        admin_user.set_password("Admin@123")
        db.session.commit()
        print("[OK] Super Admin updated.")

    # --------------------------------------------------
    # SOCIETY
    # --------------------------------------------------
    society = Society.query.filter_by(
        registration_number="MH-2024-001"
    ).first()

    if not society:
        society = Society(
            name="Sunrise Heights",
            registration_number="MH-2024-001",
            address="Plot 12, Sector 7, Andheri West",
            city="Mumbai",
            state="Maharashtra",
            pincode="400053",
            phone="022-12345678",
            email="info@sunriseheights.in",
        )
        db.session.add(society)
        db.session.commit()

    print(f"[OK] Society: {society.name} (ID={society.id})")

    # --------------------------------------------------
    # SOCIETY ADMIN
    # --------------------------------------------------
    adm = User.query.filter_by(mobile="9100000001").first()

    if not adm:
        adm = User(
            full_name="Ramesh Sharma",
            mobile="9100000001",
            email="ramesh@sunriseheights.in",
            role=Role.SOCIETY_ADMIN,
            society_id=society.id,
            account_status="ACTIVE",
            is_active=True,
        )
        adm.set_password("Admin@1234")
        db.session.add(adm)
        db.session.commit()
    else:
        adm.society_id = society.id
        adm.account_status = "ACTIVE"
        adm.is_active = True
        adm.set_password("Admin@1234")
        db.session.commit()

    print("[OK] Society Admin ready.")

    # --------------------------------------------------
    # BUILDINGS / WINGS
    # --------------------------------------------------
    buildings = []

    for wing in ["Wing A", "Wing B", "Wing C"]:
        building = Building.query.filter_by(
            society_id=society.id,
            name=wing,
        ).first()

        if not building:
            building = Building(
                society_id=society.id,
                name=wing,
                floors_count=4,
                total_flats=4,
            )
            db.session.add(building)
            db.session.commit()

        buildings.append(building)

    print(f"[OK] Wings: {[b.name for b in buildings]}")

    # --------------------------------------------------
    # FLATS
    # --------------------------------------------------
    flat_configs = [
        ("101", 1, "2BHK", 1050.0),
        ("201", 2, "2BHK", 1050.0),
        ("301", 3, "3BHK", 1500.0),
        ("401", 4, "3BHK", 1500.0),
    ]

    all_flats = []

    for building in buildings:
        prefix = building.name.split()[-1]

        for flat_no, floor, flat_type, area in flat_configs:
            full_number = f"{prefix}-{flat_no}"

            flat = Flat.query.filter_by(
                building_id=building.id,
                flat_number=full_number,
            ).first()

            if not flat:
                flat = Flat(
                    society_id=society.id,
                    building_id=building.id,
                    flat_number=full_number,
                    floor_number=floor,
                    flat_type=flat_type,
                    area_sqft=area,
                    occupancy_status="Occupied",
                )
                db.session.add(flat)
                db.session.commit()

            all_flats.append(flat)

    print(f"[OK] {len(all_flats)} flats ready.")

    # --------------------------------------------------
    # RESIDENTS + USERS
    # --------------------------------------------------
    resident_seeds = [
        ("Amit Verma", "9800000001", "amit@example.com", "Owner"),
        ("Priya Mehta", "9800000002", "priya@example.com", "Owner"),
        ("Suresh Patel", "9800000003", "suresh@example.com", "Tenant"),
        ("Kavita Singh", "9800000004", "kavita@example.com", "Owner"),
        ("Rajesh Kumar", "9800000005", "rajesh@example.com", "Tenant"),
        ("Sunita Joshi", "9800000006", "sunita@example.com", "Owner"),
    ]

    for i, (name, mobile, email, resident_type) in enumerate(
        resident_seeds
    ):
        user = User.query.filter_by(mobile=mobile).first()

        if not user:
            user = User(
                full_name=name,
                mobile=mobile,
                email=email,
                role=Role.RESIDENT,
                society_id=society.id,
                account_status="ACTIVE",
                is_active=True,
            )
            user.set_password("Resident@123")
            db.session.add(user)
            db.session.commit()

        resident = Resident.query.filter_by(user_id=user.id).first()

        if not resident:
            flat = all_flats[i]

            resident = Resident(
                flat_id=flat.id,
                user_id=user.id,
                resident_type=resident_type,
                occupancy_status="Active",
                move_in_date=date(2023, 1, 1),
                is_primary=True,
            )

            db.session.add(resident)
            db.session.commit()

    print("[OK] Residents created/verified.")

    # --------------------------------------------------
    # MAINTENANCE CONFIG
    # --------------------------------------------------
    mc = MaintenanceConfig.query.filter_by(
        society_id=society.id
    ).first()

    if not mc:
        mc = MaintenanceConfig(
            society_id=society.id,
            base_rate_per_sqft=3.5,
            fixed_monthly_rate=1500.0,
            due_day_of_month=10,
            grace_period_days=5,
            late_fee_per_month=500.0,
            billing_cycle="Monthly",
        )
        db.session.add(mc)
        db.session.commit()

    print("[OK] Maintenance config: Rs.1,500 monthly / Rs.500 late fee.")

    # --------------------------------------------------
    # MAINTENANCE BILLS
    # --------------------------------------------------
    today = date.today()

    for flat in all_flats[:6]:
        resident = Resident.query.filter_by(
            flat_id=flat.id
        ).first()

        if not resident:
            continue

        for months_ago in range(3, 0, -1):
            bill_date = today.replace(day=1) - timedelta(
                days=30 * months_ago
            )

            billing_month = bill_date.strftime("%Y-%m")

            existing = MaintenanceBill.query.filter_by(
                flat_id=flat.id,
                billing_month=billing_month,
            ).first()

            if existing:
                continue

            amount = mc.fixed_monthly_rate
            paid = months_ago == 3

            bill = MaintenanceBill(
                bill_number=f"BILL-{flat.id}-{billing_month}",
                flat_id=flat.id,
                resident_id=resident.id,
                billing_month=billing_month,
                base_amount=amount,
                total_amount=amount,
                amount_paid=amount if paid else 0.0,
                remaining_amount=0.0 if paid else amount,
                due_date=bill_date.replace(day=mc.due_day_of_month),
                status="Paid" if paid else "Pending",
            )

            db.session.add(bill)

    db.session.commit()
    print("[OK] Maintenance bills created/verified.")

    # --------------------------------------------------
    # COMPLAINT CATEGORIES
    # --------------------------------------------------
    categories = [
        "Plumbing",
        "Electrical",
        "Lift",
        "Security",
        "Housekeeping",
        "Noise",
        "Parking",
        "Common Area",
    ]

    for category_name in categories:
        existing = ComplaintCategory.query.filter_by(
            name=category_name
        ).first()

        if not existing:
            db.session.add(
                ComplaintCategory(name=category_name)
            )

    db.session.commit()

    # --------------------------------------------------
    # SAMPLE COMPLAINTS
    # --------------------------------------------------
    residents_list = Resident.query.filter_by(
        society_id=society.id
    ).all()

    existing_complaint = Complaint.query.filter_by(
        society_id=society.id
    ).first()

    if residents_list and not existing_complaint:
        sample_categories = [
            "Plumbing",
            "Electrical",
            "Lift",
        ]

        for i, resident in enumerate(residents_list[:3]):
            complaint = Complaint(
                ticket_number=f"TKT-{society.id}-{i + 1:04d}",
                flat_id=resident.flat_id,
                resident_id=resident.id,
                category=sample_categories[i],
                title=f"Sample Complaint #{i + 1}",
                description="Demo complaint for testing.",
                priority="Medium",
                status="Submitted",
            )
            db.session.add(complaint)

        db.session.commit()

    print("[OK] Complaint categories and samples ready.")

    # --------------------------------------------------
    # FACILITIES
    # --------------------------------------------------
    facilities_data = [
        ("Clubhouse", 50, 0.0, False),
        ("Swimming Pool", 30, 0.0, False),
        ("Gymnasium", 20, 0.0, False),
        ("Banquet Hall", 100, 500.0, True),
        ("Tennis Court", 10, 100.0, True),
    ]

    for name, capacity, hourly_rate, approval in facilities_data:
        existing = Facility.query.filter_by(
            society_id=society.id,
            name=name,
        ).first()

        if not existing:
            facility = Facility(
                society_id=society.id,
                name=name,
                capacity=capacity,
                hourly_rate=hourly_rate,
                is_active=True,
                requires_approval=approval,
            )
            db.session.add(facility)

    db.session.commit()
    print("[OK] Facilities seeded.")

    # --------------------------------------------------
    # STAFF
    # --------------------------------------------------
    staff_data = [
        ("Ramu Kaka", "Security", "9900000001", 15000.0),
        ("Ganesh Sweep", "Housekeeping", "9900000002", 12000.0),
        ("Suresh Gate", "Security", "9900000003", 15000.0),
        ("Maintenance Man", "Plumber", "9900000004", 18000.0),
    ]

    for name, role_type, phone, salary in staff_data:
        existing = Staff.query.filter_by(
            society_id=society.id,
            phone=phone,
        ).first()

        if not existing:
            staff = Staff(
                society_id=society.id,
                full_name=name,
                role_type=role_type,
                phone=phone,
                salary_amount=salary,
                status="Active",
                joining_date=date(2023, 6, 1),
            )
            db.session.add(staff)

    db.session.commit()
    print("[OK] Staff seeded.")

    # --------------------------------------------------
    # NOTICES
    # --------------------------------------------------
    existing_notice = Notice.query.filter_by(
        society_id=society.id
    ).first()

    if not existing_notice:
        notices = [
            (
                "Annual General Meeting",
                "The AGM for FY 2024-25 is scheduled on 15th September at 6 PM in the Clubhouse.",
                "Meeting",
                "Normal",
            ),
            (
                "Maintenance Due Reminder",
                "All residents are reminded to pay monthly maintenance by the 10th to avoid penalty.",
                "Maintenance",
                "High",
            ),
            (
                "Water Supply Disruption",
                "Water supply will be interrupted on Sunday from 10 AM - 2 PM for pipeline maintenance.",
                "Water",
                "Urgent",
            ),
        ]

        for title, content, notice_type, priority in notices:
            notice = Notice(
                society_id=society.id,
                title=title,
                content=content,
                notice_type=notice_type,
                priority=priority,
                created_by_id=adm.id,
                publish_date=utcnow(),
            )
            db.session.add(notice)

        db.session.commit()

    print("[OK] Notices seeded.")

    # --------------------------------------------------
    # SECURITY GUARD
    # --------------------------------------------------
    guard = User.query.filter_by(
        mobile="9700000001"
    ).first()

    if not guard:
        guard = User(
            full_name="Gate Security",
            mobile="9700000001",
            email="guard@sunriseheights.in",
            role=Role.SECURITY,
            society_id=society.id,
            account_status="ACTIVE",
            is_active=True,
        )
        guard.set_password("Guard@1234")
        db.session.add(guard)
        db.session.commit()

    print("[OK] Security Guard ready.")

    # --------------------------------------------------
    # FINAL
    # --------------------------------------------------
    print()
    print("=" * 60)
    print("DATABASE SEEDED SUCCESSFULLY!")
    print("=" * 60)
    print()
    print("LOGIN CREDENTIALS")
    print("  Super Admin   : username=admin  password=Admin@123")
    print("  Society Admin : mobile=9100000001  password=Admin@1234")
    print("  Resident 1    : mobile=9800000001  password=Resident@123")
    print("  Security Guard: mobile=9700000001  password=Guard@1234")
    print()
    print("Run the app : python run.py")
    print("Open browser: http://127.0.0.1:5000")
