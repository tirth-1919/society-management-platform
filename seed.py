"""
Society Management SaaS - Production-Safe Database Seeder

Run with:
    python seed.py

IMPORTANT:
- Does NOT delete existing production data.
- Does NOT reset passwords of existing users.
- Creates only missing seed records.
- Safe to run multiple times.
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
from app.services.tenant_service import TenantService
from app.utils import utcnow


# --------------------------------------------------
# ENVIRONMENT
# --------------------------------------------------

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

app = create_app()


# ==================================================
# HELPER FUNCTIONS
# ==================================================

def get_or_create_user(
    mobile,
    full_name,
    email,
    role,
    society_id,
    password,
    username=None,
):
    """
    Production-safe user creation.

    If the user already exists:
        - Do NOT change password.
        - Do NOT change account status.
        - Do NOT change role.
        - Do NOT change society.

    If the user does not exist:
        - Create the user with the supplied values.
    """

    user = User.query.filter_by(
        mobile=mobile
    ).first()

    if user:
        print(
            f"[EXISTS] User already exists: "
            f"{mobile}"
        )

        return user

    user = User(
        full_name=full_name,
        mobile=mobile,
        email=email,
        role=role,
        society_id=society_id,
        account_status="ACTIVE",
        is_active=True,
    )

    if username:
        user.username = username

    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    print(
        f"[CREATED] User: "
        f"{full_name} ({mobile})"
    )

    return user


# ==================================================
# DATABASE SEED
# ==================================================

with app.app_context():

    print()
    print("=" * 70)
    print("PRODUCTION-SAFE DATABASE SEED")
    print("=" * 70)
    print()

    # --------------------------------------------------
    # DATABASE TABLES
    # --------------------------------------------------

    # IMPORTANT:
    # create_all() creates missing tables only.
    # It does NOT delete existing rows.
    db.create_all()

    print(
        "[OK] Database tables created/verified."
    )

    # ==================================================
    # SUPER ADMIN
    # ==================================================

    print()
    print("-" * 70)
    print("SUPER ADMIN")
    print("-" * 70)

    admin_user = User.query.filter(
        (User.username == "admin") |
        (User.mobile == "9000000000")
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

        admin_user.set_password(
            "Admin@123"
        )

        db.session.add(admin_user)
        db.session.commit()

        print(
            "[CREATED] Super Admin"
        )
        print(
            "          username: admin"
        )
        print(
            "          password: Admin@123"
        )

    else:

        print(
            "[EXISTS] Super Admin already exists."
        )

        print(
            "[SAFE] Existing Super Admin "
            "password was NOT changed."
        )

    # ==================================================
    # SOCIETY
    # ==================================================

    print()
    print("-" * 70)
    print("SOCIETY")
    print("-" * 70)

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

        print(
            "[CREATED] Society: "
            "Sunrise Heights"
        )

    else:

        print(
            f"[EXISTS] Society: "
            f"{society.name} "
            f"(ID={society.id})"
        )

    # ==================================================
    # SOCIETY ADMIN
    # ==================================================

    print()
    print("-" * 70)
    print("SOCIETY ADMIN")
    print("-" * 70)

    adm = User.query.filter_by(
        mobile="9100000001"
    ).first()

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

        adm.set_password(
            "Admin@1234"
        )

        db.session.add(adm)
        db.session.commit()

        print(
            "[CREATED] Society Admin"
        )
        print(
            "          mobile: 9100000001"
        )
        print(
            "          password: Admin@1234"
        )

    else:

        print(
            "[EXISTS] Society Admin already exists."
        )

        print(
            "[SAFE] Existing Society Admin "
            "password was NOT changed."
        )

    # ==================================================
    # BLOCKS + FLATS
    # ==================================================

    print()
    print("-" * 70)
    print("BLOCKS + FLATS")
    print("-" * 70)

    TenantService.ensure_default_blocks_and_flats(
        society.id
    )

    buildings = (
        Building.query
        .filter_by(
            society_id=society.id
        )
        .order_by(
            Building.name.asc()
        )
        .all()
    )

    all_flats = (
        Flat.query
        .filter_by(
            society_id=society.id
        )
        .order_by(
            Flat.building_id.asc(),
            Flat.floor_number.asc(),
            Flat.flat_number.asc(),
        )
        .all()
    )

    print(
        f"[OK] Blocks: "
        f"{[b.name for b in buildings]}"
    )

    print(
        f"[OK] {len(all_flats)} flats "
        f"ready across all blocks."
    )

    # ==================================================
    # RESIDENT USERS
    # ==================================================

    print()
    print("-" * 70)
    print("RESIDENT USERS")
    print("-" * 70)

    resident_seeds = [
        (
            "Amit Verma",
            "9800000001",
            "amit@example.com",
            "Owner",
        ),
        (
            "Priya Mehta",
            "9800000002",
            "priya@example.com",
            "Owner",
        ),
        (
            "Suresh Patel",
            "9800000003",
            "suresh@example.com",
            "Tenant",
        ),
        (
            "Kavita Singh",
            "9800000004",
            "kavita@example.com",
            "Owner",
        ),
        (
            "Rajesh Kumar",
            "9800000005",
            "rajesh@example.com",
            "Tenant",
        ),
        (
            "Sunita Joshi",
            "9800000006",
            "sunita@example.com",
            "Owner",
        ),
    ]

    for i, (
        name,
        mobile,
        email,
        resident_type,
    ) in enumerate(
        resident_seeds
    ):

        user = User.query.filter_by(
            mobile=mobile
        ).first()

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

            user.set_password(
                "Resident@123"
            )

            db.session.add(user)
            db.session.commit()

            print(
                f"[CREATED] Resident User: "
                f"{name}"
            )

        else:

            print(
                f"[EXISTS] Resident User: "
                f"{mobile}"
            )

        # ------------------------------------------
        # RESIDENT PROFILE
        # ------------------------------------------

        resident = Resident.query.filter_by(
            user_id=user.id
        ).first()

        if resident:

            print(
                f"[EXISTS] Resident Profile: "
                f"{name}"
            )

            continue

        # Prevent index error if fewer flats exist.
        if i >= len(all_flats):

            print(
                f"[WARNING] No available flat "
                f"for {name}"
            )

            continue

        flat = all_flats[i]

        resident = Resident(
            society_id=society.id,
            flat_id=flat.id,
            user_id=user.id,
            full_name=name,
            mobile=mobile,
            email=email,
            resident_type=resident_type,
            occupancy_status="Active",
            move_in_date=date(
                2023,
                1,
                1,
            ),
            is_primary=True,
        )

        db.session.add(resident)
        db.session.commit()

        print(
            f"[CREATED] Resident Profile: "
            f"{name} -> Flat "
            f"{flat.flat_number}"
        )

    print(
        "[OK] Residents created/verified."
    )

    # ==================================================
    # MAINTENANCE CONFIG
    # ==================================================

    print()
    print("-" * 70)
    print("MAINTENANCE CONFIGURATION")
    print("-" * 70)

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

        print(
            "[CREATED] Maintenance configuration."
        )

    else:

        print(
            "[EXISTS] Maintenance configuration."
        )

    print(
        "[OK] Monthly maintenance: Rs.1,500"
    )

    print(
        "[OK] Late fee: Rs.500/month"
    )

    # ==================================================
    # MAINTENANCE BILLS
    # ==================================================

    print()
    print("-" * 70)
    print("MAINTENANCE BILLS")
    print("-" * 70)

    today = date.today()

    # Keep your existing behavior:
    # first 6 flats only.
    for flat in all_flats[:6]:

        resident = Resident.query.filter_by(
            flat_id=flat.id
        ).first()

        if not resident:

            print(
                f"[SKIP] No resident for "
                f"flat {flat.flat_number}"
            )

            continue

        for months_ago in range(3, 0, -1):

            bill_date = (
                today.replace(day=1)
                - timedelta(
                    days=30 * months_ago
                )
            )

            billing_month = (
                bill_date.strftime("%Y-%m")
            )

            existing = (
                MaintenanceBill.query
                .filter_by(
                    flat_id=flat.id,
                    billing_month=billing_month,
                )
                .first()
            )

            if existing:

                print(
                    f"[EXISTS] Bill "
                    f"{billing_month} "
                    f"for Flat "
                    f"{flat.flat_number}"
                )

                continue

            amount = (
                mc.fixed_monthly_rate
            )

            # Oldest of the three sample bills
            # is marked Paid.
            #
            # Newer two are Pending.
            paid = months_ago == 3

            bill = MaintenanceBill(
                society_id=society.id,
                bill_number=(
                    f"BILL-{flat.id}-"
                    f"{billing_month}"
                ),
                flat_id=flat.id,
                resident_id=resident.id,
                billing_month=billing_month,
                base_amount=amount,
                total_amount=amount,
                amount_paid=(
                    amount
                    if paid
                    else 0.0
                ),
                remaining_amount=(
                    0.0
                    if paid
                    else amount
                ),
                due_date=bill_date.replace(
                    day=mc.due_day_of_month
                ),
                status=(
                    "Paid"
                    if paid
                    else "Pending"
                ),
            )

            db.session.add(bill)

            print(
                f"[CREATED] Bill "
                f"{billing_month} "
                f"for Flat "
                f"{flat.flat_number} "
                f"-> "
                f"{'PAID' if paid else 'PENDING'}"
            )

    db.session.commit()

    print(
        "[OK] Maintenance bills "
        "created/verified."
    )

    # ==================================================
    # COMPLAINT CATEGORIES
    # ==================================================

    print()
    print("-" * 70)
    print("COMPLAINT CATEGORIES")
    print("-" * 70)

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

        existing = (
            ComplaintCategory.query
            .filter_by(
                name=category_name
            )
            .first()
        )

        if existing:

            print(
                f"[EXISTS] Category: "
                f"{category_name}"
            )

            continue

        db.session.add(
            ComplaintCategory(
                name=category_name
            )
        )

        print(
            f"[CREATED] Category: "
            f"{category_name}"
        )

    db.session.commit()

    # ==================================================
    # SAMPLE COMPLAINTS
    # ==================================================

    print()
    print("-" * 70)
    print("SAMPLE COMPLAINTS")
    print("-" * 70)

    residents_list = (
        Resident.query
        .filter_by(
            society_id=society.id
        )
        .all()
    )

    existing_complaint = (
        Complaint.query
        .filter_by(
            society_id=society.id
        )
        .first()
    )

    if residents_list and not existing_complaint:

        sample_categories = [
            "Plumbing",
            "Electrical",
            "Lift",
        ]

        for i, resident in enumerate(
            residents_list[:3]
        ):

            complaint = Complaint(
                society_id=society.id,
                ticket_number=(
                    f"TKT-{society.id}-"
                    f"{i + 1:04d}"
                ),
                flat_id=resident.flat_id,
                resident_id=resident.id,
                category=sample_categories[i],
                title=(
                    f"Sample Complaint #{i + 1}"
                ),
                description=(
                    "Demo complaint for testing."
                ),
                priority="Medium",
                status="Submitted",
            )

            db.session.add(complaint)

            print(
                f"[CREATED] Complaint #{i + 1}"
            )

        db.session.commit()

    else:

        print(
            "[EXISTS] Complaint data already exists."
        )

    print(
        "[OK] Complaint categories "
        "and samples ready."
    )

    # ==================================================
    # FACILITIES
    # ==================================================

    print()
    print("-" * 70)
    print("FACILITIES")
    print("-" * 70)

    facilities_data = [
        (
            "Club House",
            50,
            0.0,
            False,
        ),
        (
            "Swimming Pool",
            30,
            0.0,
            False,
        ),
        (
            "Gym",
            20,
            0.0,
            False,
        ),
        (
            "Community Hall",
            100,
            500.0,
            True,
        ),
        (
            "Party Hall",
            80,
            400.0,
            True,
        ),
        (
            "Indoor Games Room",
            25,
            0.0,
            False,
        ),
        (
            "Badminton Court",
            10,
            100.0,
            False,
        ),
        (
            "Tennis Court",
            10,
            100.0,
            True,
        ),
        (
            "Garden",
            100,
            0.0,
            False,
        ),
        (
            "Children's Play Area",
            40,
            0.0,
            False,
        ),
    ]

    for (
        name,
        capacity,
        hourly_rate,
        approval,
    ) in facilities_data:

        existing = (
            Facility.query
            .filter_by(
                society_id=society.id,
                name=name,
            )
            .first()
        )

        if existing:

            print(
                f"[EXISTS] Facility: {name}"
            )

            continue

        facility = Facility(
            society_id=society.id,
            name=name,
            capacity=capacity,
            hourly_rate=hourly_rate,
            is_active=True,
            requires_approval=approval,
        )

        db.session.add(facility)

        print(
            f"[CREATED] Facility: {name}"
        )

    db.session.commit()

    print(
        "[OK] Facilities seeded."
    )

    # ==================================================
    # STAFF
    # ==================================================

    print()
    print("-" * 70)
    print("STAFF")
    print("-" * 70)

    staff_data = [
        (
            "Ramu Kaka",
            "Security",
            "9900000001",
            15000.0,
        ),
        (
            "Ganesh Sweep",
            "Housekeeping",
            "9900000002",
            12000.0,
        ),
        (
            "Suresh Gate",
            "Security",
            "9900000003",
            15000.0,
        ),
        (
            "Maintenance Man",
            "Plumber",
            "9900000004",
            18000.0,
        ),
    ]

    for (
        name,
        role_type,
        phone,
        salary,
    ) in staff_data:

        existing = (
            Staff.query
            .filter_by(
                society_id=society.id,
                phone=phone,
            )
            .first()
        )

        if existing:

            print(
                f"[EXISTS] Staff: {name}"
            )

            continue

        staff = Staff(
            society_id=society.id,
            full_name=name,
            role_type=role_type,
            phone=phone,
            salary_amount=salary,
            status="Active",
            joining_date=date(
                2023,
                6,
                1,
            ),
        )

        db.session.add(staff)

        print(
            f"[CREATED] Staff: {name}"
        )

    db.session.commit()

    print(
        "[OK] Staff seeded."
    )

    # ==================================================
    # NOTICES
    # ==================================================

    print()
    print("-" * 70)
    print("NOTICES")
    print("-" * 70)

    existing_notice = (
        Notice.query
        .filter_by(
            society_id=society.id
        )
        .first()
    )

    if not existing_notice:

        notices = [
            (
                "Annual General Meeting",
                (
                    "The AGM for FY 2024-25 "
                    "is scheduled on 15th September "
                    "at 6 PM in the Clubhouse."
                ),
                "Meeting",
                "Normal",
            ),
            (
                "Maintenance Due Reminder",
                (
                    "All residents are reminded "
                    "to pay monthly maintenance "
                    "by the 10th to avoid penalty."
                ),
                "Maintenance",
                "High",
            ),
            (
                "Water Supply Disruption",
                (
                    "Water supply will be interrupted "
                    "on Sunday from 10 AM - 2 PM "
                    "for pipeline maintenance."
                ),
                "Water",
                "Urgent",
            ),
        ]

        for (
            title,
            content,
            notice_type,
            priority,
        ) in notices:

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

            print(
                f"[CREATED] Notice: {title}"
            )

        db.session.commit()

    else:

        print(
            "[EXISTS] Notices already exist."
        )

    print(
        "[OK] Notices seeded."
    )

    # ==================================================
    # SECURITY GUARD
    # ==================================================

    print()
    print("-" * 70)
    print("SECURITY USER")
    print("-" * 70)

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

        guard.set_password(
            "Guard@1234"
        )

        db.session.add(guard)
        db.session.commit()

        print(
            "[CREATED] Security Guard"
        )

        print(
            "          mobile: 9700000001"
        )

        print(
            "          password: Guard@1234"
        )

    else:

        print(
            "[EXISTS] Security Guard already exists."
        )

        print(
            "[SAFE] Existing password "
            "was NOT changed."
        )

    # ==================================================
    # FINAL SUMMARY
    # ==================================================

    print()
    print("=" * 70)
    print("DATABASE SEED COMPLETED SUCCESSFULLY")
    print("=" * 70)
    print()

    print(
        "IMPORTANT:"
    )

    print(
        "  Existing production data was NOT deleted."
    )

    print(
        "  Existing user passwords were NOT changed."
    )

    print(
        "  Existing bills were NOT duplicated."
    )

    print()

    print(
        "NEW LOGIN CREDENTIALS "
        "(only if these users did not already exist):"
    )

    print()

    print(
        "Super Admin"
    )
    print(
        "  Username : admin"
    )
    print(
        "  Password : Admin@123"
    )

    print()

    print(
        "Society Admin"
    )
    print(
        "  Mobile   : 9100000001"
    )
    print(
        "  Password : Admin@1234"
    )

    print()

    print(
        "Resident"
    )
    print(
        "  Mobile   : 9800000001"
    )
    print(
        "  Password : Resident@123"
    )

    print()

    print(
        "Security Guard"
    )
    print(
        "  Mobile   : 9700000001"
    )
    print(
        "  Password : Guard@1234"
    )

    print()

    print("=" * 70)
    print("DONE")
    print("=" * 70)