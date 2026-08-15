from app.utils import utcnow
from datetime import datetime
from flask import abort
from app.models import (
    db,
    User,
    Role,
    Society,
    Building,
    Block,
    Flat,
    Resident,
    RegistrationRequest,
    AuditLog,
)
from app.config import Config
from app.services.auth_service import AuthService

# â”€â”€â”€ Constants (server-side, never trust frontend amounts) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
MONTHLY_MAINTENANCE_RATE = 1500.0  # ₹1,500 per month
LATE_FEE_PER_MONTH = 500.0  # ₹500 per overdue month


class RegistrationService:
    @staticmethod
    def validate_hierarchy(society_id, building_id, block_id, flat_id):
        """
        Validates that society â†’ wing (building) â†’ block â†’ flat hierarchy is
        internally consistent. Aborts 403 if any ID is tampered / mismatched.

        block_id is REQUIRED (not optional) for new registrations.
        """
        society = db.session.get(Society, society_id)
        if not society:
            abort(403, description="Forbidden: Invalid society selected")

        # Wing must belong to society
        wing = Building.query.filter_by(id=building_id, society_id=society_id).first()
        if not wing:
            abort(
                403, description="Forbidden: Wing does not belong to selected society"
            )

        # Block must belong to wing and society
        block = Block.query.filter_by(
            id=block_id, building_id=building_id, society_id=society_id
        ).first()
        if not block:
            abort(
                403,
                description="Forbidden: Block does not belong to selected wing/society",
            )

        # Flat must belong to block, wing and society
        flat = Flat.query.filter_by(
            id=flat_id,
            block_id=block_id,
            building_id=building_id,
            society_id=society_id,
        ).first()
        if not flat:
            abort(
                403,
                description="Forbidden: Flat does not belong to selected block/wing/society",
            )

        return society, wing, block, flat

    @staticmethod
    def validate_hierarchy_legacy(society_id, building_id, flat_id):
        """
        Backward-compatible validation for tests that don't use blocks.
        Validates society â†’ building â†’ flat only.
        Used by existing tests and internal calls without block_id.
        """
        society = db.session.get(Society, society_id)
        if not society:
            abort(403, description="Forbidden: Invalid society selected")

        building = Building.query.filter_by(
            id=building_id, society_id=society_id
        ).first()
        if not building:
            abort(
                403,
                description="Forbidden: Building does not belong to selected society",
            )

        flat = Flat.query.filter_by(
            id=flat_id, building_id=building_id, society_id=society_id
        ).first()
        if not flat:
            abort(
                403,
                description="Forbidden: Flat does not belong to selected building or society",
            )

        return society, building, flat

    @staticmethod
    def register_resident(
        full_name,
        mobile,
        email,
        society_id,
        building_id,
        flat_id,
        occupancy_type,
        password,
        block_id=None,
    ):
        """
        Registers a new resident:
        1. Validates hierarchy (Wingâ†’Blockâ†’Flat when block_id given, else Wingâ†’Flat).
        2. Checks duplicate active/pending accounts.
        3. Hashes password into User model ONLY. (Never in RegistrationRequest).
        4. Creates RegistrationRequest record.
        """
        mobile = AuthService.normalize_mobile(mobile)
        if block_id is not None:
            society, wing, block, flat = RegistrationService.validate_hierarchy(
                society_id, building_id, block_id, flat_id
            )
        else:
            society, building, flat = RegistrationService.validate_hierarchy_legacy(
                society_id, building_id, flat_id
            )

        # Check existing user with this mobile
        existing_user = User.query.filter_by(mobile=mobile).first()
        if existing_user:
            if existing_user.account_status == "ACTIVE":
                raise ValueError("Mobile number already registered and active.")
            elif existing_user.account_status == "PENDING_APPROVAL":
                pending_req = RegistrationRequest.query.filter_by(
                    user_id=existing_user.id, status="PENDING_APPROVAL"
                ).first()
                if pending_req:
                    return pending_req
            elif existing_user.account_status == "REJECTED":
                existing_user.full_name = full_name
                existing_user.email = email
                existing_user.society_id = society_id
                existing_user.account_status = "PENDING_APPROVAL"
                existing_user.is_active = False
                existing_user.set_password(password)
                db.session.commit()

                req = RegistrationRequest(
                    user_id=existing_user.id,
                    society_id=society_id,
                    building_id=building_id,
                    block_id=block_id,
                    flat_id=flat_id,
                    full_name=full_name,
                    mobile=mobile,
                    email=email,
                    occupancy_type=occupancy_type,
                    status="PENDING_APPROVAL",
                )
                db.session.add(req)
                db.session.commit()
                return req

        # Create new User
        user = User(
            full_name=full_name,
            mobile=mobile,
            email=email,
            society_id=society_id,
            role=Role.RESIDENT,
            account_status="PENDING_APPROVAL",
            is_active=False,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        req = RegistrationRequest(
            user_id=user.id,
            society_id=society_id,
            building_id=building_id,
            block_id=block_id,
            flat_id=flat_id,
            full_name=full_name,
            mobile=mobile,
            email=email,
            occupancy_type=occupancy_type,
            status="PENDING_APPROVAL",
        )
        db.session.add(req)
        db.session.commit()
        return req

    @staticmethod
    def approve_request(registration_id, admin_user):
        """Approves a registration request."""
        req = db.session.get(RegistrationRequest, registration_id)
        if not req:
            raise ValueError("Registration request not found")

        if (
            admin_user.role != Role.SUPER_ADMIN
            and admin_user.society_id != req.society_id
        ):
            abort(
                403,
                description="Forbidden: Cannot approve registration for another society",
            )

        req.status = "APPROVED"
        req.approved_by_id = admin_user.id
        req.approved_at = utcnow()

        user = db.session.get(User, req.user_id)
        if user:
            user.maintenance_start_month = req.approved_at.strftime("%Y-%m")
            user.account_status = "ACTIVE"
            user.is_active = True
            user.society_id = req.society_id

            existing_resident = Resident.query.filter_by(
                user_id=user.id, flat_id=req.flat_id
            ).first()
            if not existing_resident:
                res_type = (
                    "Owner" if req.occupancy_type in ["OWNER", "Owner"] else "Tenant"
                )
                existing_resident = Resident(
                    society_id=req.society_id,
                    flat_id=req.flat_id,
                    user_id=user.id,
                    full_name=user.full_name,
                    mobile=user.mobile,
                    email=user.email,
                    resident_type=res_type,
                    occupancy_status="Active",
                    is_primary=True,
                )
                db.session.add(existing_resident)
                db.session.flush()

            from app.services.billing_service import BillingService

            BillingService.ensure_bill_for_flat(
                society_id=req.society_id,
                flat_id=req.flat_id,
                resident_id=existing_resident.id,
                billing_month=user.maintenance_start_month,
            )

        audit = AuditLog(
            society_id=req.society_id,
            user_id=admin_user.id,
            action="RESIDENT_REGISTRATION_APPROVED",
            details=f"Approved registration #{req.id} for user {user.full_name if user else req.full_name}",
        )
        db.session.add(audit)
        db.session.commit()
        return req

    @staticmethod
    def reject_request(registration_id, admin_user, reason):
        """Rejects a registration request."""
        req = db.session.get(RegistrationRequest, registration_id)
        if not req:
            raise ValueError("Registration request not found")

        if (
            admin_user.role != Role.SUPER_ADMIN
            and admin_user.society_id != req.society_id
        ):
            abort(
                403,
                description="Forbidden: Cannot reject registration for another society",
            )

        req.status = "REJECTED"
        req.rejection_reason = reason
        req.rejected_by_id = admin_user.id
        req.rejected_at = utcnow()

        user = db.session.get(User, req.user_id)
        if user:
            user.account_status = "REJECTED"
            user.is_active = False

        audit = AuditLog(
            society_id=req.society_id,
            user_id=admin_user.id,
            action="RESIDENT_REGISTRATION_REJECTED",
            details=f"Rejected registration #{req.id} for reason: {reason}",
        )
        db.session.add(audit)
        db.session.commit()
        return req


# â”€â”€â”€ Maintenance Due Calculator â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class MaintenanceSummaryService:
    """
    Server-side maintenance due calculator.
    Uses actual unpaid MaintenanceBill records â€” never trusts frontend.

    Rates (fixed, server-side):
        Monthly maintenance: ₹1,500
        Late fee per unpaid month: ₹500
    """

    MONTHLY_RATE = Config.MONTHLY_MAINTENANCE
    LATE_FEE_RATE = Config.LATE_FEE_PER_MONTH

    @staticmethod
    def calculate_dues(flat_id=None, user_id=None, as_of=None):
        """
        Returns a dict with:
            current_month_maintenance: ₹1,500 by default (or the society's configured rate)
            pending_months: count of unpaid months before the current billing month
            maintenance_due: all unpaid bill base amounts, including the current month
            late_fee: ₹500 for each unpaid month before the current billing month
            total_due: maintenance_due + late_fee
        """
        from app.models import MaintenanceBill, User, MaintenanceConfig

        if user_id is not None:
            user = db.session.get(User, user_id)
            resident = Resident.query.filter_by(
                user_id=user_id, is_primary=True
            ).first()
            flat_id = resident.flat_id if resident else None
        else:
            resident = Resident.query.filter_by(
                flat_id=flat_id, is_primary=True
            ).first()
            user = resident.user if resident else None

        as_of = as_of or utcnow().date()
        config = (
            MaintenanceConfig.query.filter_by(society_id=user.society_id).first()
            if user
            else None
        )
        monthly_rate = (
            config.fixed_monthly_rate
            if config
            else MaintenanceSummaryService.MONTHLY_RATE
        )
        late_fee_rate = (
            config.late_fee_per_month
            if config
            else MaintenanceSummaryService.LATE_FEE_RATE
        )
        resident_id = resident.id if resident else None
        # Bills belong to a resident's occupancy, not merely the physical flat.
        # This prevents a newly approved resident from inheriting a predecessor's dues.
        bill_query = (
            MaintenanceBill.query.filter_by(resident_id=resident_id)
            if resident_id
            else MaintenanceBill.query.filter_by(flat_id=flat_id)
        )
        existing_bills = bill_query.all() if flat_id else []
        start_month = user.maintenance_start_month if user else None
        if not existing_bills and not start_month:
            start_month = Config.MAINTENANCE_DEFAULT_START_MONTH

        unpaid_bills = (
            bill_query.filter(
                MaintenanceBill.status.in_(["Pending", "Partially Paid", "Overdue"])
            )
            .order_by(MaintenanceBill.billing_month.asc())
            .all()
        )

        virtual_months = []
        if not existing_bills and start_month:
            year, month = map(int, start_month.split("-"))
            while (year, month) <= (as_of.year, as_of.month):
                virtual_months.append(f"{year:04d}-{month:02d}")
                month += 1
                if month == 13:
                    year, month = year + 1, 1

        current_month = as_of.strftime("%Y-%m")
        # The current charge is payable, but it is not an old pending month.
        pending_months = (
            sum(1 for bill in unpaid_bills if bill.billing_month < current_month)
            if existing_bills
            else sum(
                1 for billing_month in virtual_months if billing_month < current_month
            )
        )
        maintenance_due = (
            sum(b.base_amount for b in unpaid_bills)
            if existing_bills
            else len(virtual_months) * monthly_rate
        )
        # A late fee is only assessed for a prior billing month that is past its due date.
        overdue_months = sum(
            1
            for bill in unpaid_bills
            if bill.billing_month < current_month
            and bill.due_date
            and bill.due_date < as_of
        )
        if not existing_bills and virtual_months:
            overdue_months = sum(
                1
                for billing_month in virtual_months
                if billing_month < current_month
                and datetime.strptime(billing_month, "%Y-%m")
                .date()
                .replace(day=min(Config.MAINTENANCE_DUE_DAY, 28))
                < as_of
            )
        late_fee = overdue_months * late_fee_rate
        total_due = maintenance_due + late_fee

        return {
            "current_month_maintenance": monthly_rate,
            "pending_months": pending_months,
            "overdue_months": overdue_months,
            "maintenance_start_month": start_month,
            "billing_months": [b.billing_month for b in unpaid_bills] or virtual_months,
            "maintenance_due": maintenance_due,
            "late_fee": late_fee,
            "total_due": total_due,
            "unpaid_bills": unpaid_bills,
        }




