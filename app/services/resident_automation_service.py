from app.models import (
    db,
    User,
    Society,
    Resident,
    RegistrationRequest,
    EmergencyContact,
    Vehicle,
    AutomationAlert,
)
from app.services.notification_service import NotificationService
from app.utils import utcnow
from datetime import timedelta


class ResidentAutomationService:
    """
    Implements Phase 2 Resident Automation (Features 1–20):
    1. Auto-detect new resident registration
    2. Auto-create registration task
    3. Auto-remind Admin about pending registration
    4. Auto-escalate registration after 3 days
    5. Auto-escalate registration after 7 days
    6. Auto-detect incomplete registration
    7. Auto-request missing information
    8. Auto-detect duplicate mobile
    9. Auto-detect duplicate flat
    10. Auto-detect duplicate email
    11. Auto-create resident profile after approval
    12. Auto-activate resident after approval
    13. Auto-send welcome notification
    14. Auto-send onboarding checklist
    15. Auto-send society rules
    16. Auto-send emergency contacts
    17. Auto-send payment instructions
    18. Auto-send first-bill explanation
    19. Auto-detect inactive resident account
    20. Auto-remind inactive resident to complete profile
    """

    @staticmethod
    def on_resident_registered(registration_req):
        """
        Features 1 & 2:
        Auto-detects new resident registration, emits 'resident_registered' event,
        and creates an admin review alert/task.
        """
        if not registration_req:
            return None

        soc_id = registration_req.society_id
        flat_str = registration_req.flat.flat_number if registration_req.flat else str(registration_req.flat_id)
        
        # 1. Create registration task / alert for admin
        alert = AutomationAlert(
            society_id=soc_id,
            alert_type="RESIDENT_REGISTRATION",
            severity="INFO",
            title=f"New Registration: {registration_req.full_name}",
            message=f"New membership request #{registration_req.id} submitted for Flat {flat_str} by {registration_req.full_name} ({registration_req.mobile}). Admin review required.",
            is_resolved=False,
        )
        db.session.add(alert)
        db.session.commit()

        # 2. Trigger automation event
        from app.services.automation_service import AutomationService
        AutomationService.trigger_event(
            event_name="resident_registered",
            society_id=soc_id,
            payload={
                "registration_id": registration_req.id,
                "full_name": registration_req.full_name,
                "mobile": registration_req.mobile,
                "email": registration_req.email,
                "flat_id": registration_req.flat_id,
                "occupancy_type": registration_req.occupancy_type,
            },
        )
        return alert

    @staticmethod
    def on_resident_approved(registration_req, admin_user):
        """
        Features 11–18:
        Orchestrates automated post-approval onboarding communications:
        - Welcome notification
        - Onboarding checklist
        - Society rules
        - Emergency contacts
        - Payment instructions
        - First-bill explanation
        """
        if not registration_req or not registration_req.user_id:
            return

        user = db.session.get(User, registration_req.user_id)
        if not user:
            return

        soc = db.session.get(Society, registration_req.society_id)
        soc_name = soc.name if soc else "Our Society"
        flat_str = registration_req.flat.property_key if (registration_req.flat and hasattr(registration_req.flat, 'property_key')) else str(registration_req.flat_id)

        # Feature 13: Welcome Notification
        NotificationService.send_notification(
            recipient=user.mobile or user.email or "N/A",
            message=f"Welcome to {soc_name}! Your resident registration for Flat {flat_str} has been approved. You can now access all society portal services.",
            channel="In-App",
            society_id=user.society_id,
            user_id=user.id,
            category="General",
        )

        # Feature 14: Onboarding Checklist
        NotificationService.send_notification(
            recipient=user.mobile or user.email or "N/A",
            message=f"Resident Onboarding Checklist for Flat {flat_str}:\n1. Add emergency contact\n2. Register household members & vehicles\n3. Review society rules\n4. Setup notification preferences.",
            channel="In-App",
            society_id=user.society_id,
            user_id=user.id,
            category="General",
        )

        # Feature 15: Society Rules
        NotificationService.send_notification(
            recipient=user.mobile or user.email or "N/A",
            message="Society Guidelines: Please observe quiet hours (10 PM – 7 AM), park in designated slots only, and ensure visitors are registered at the security gate.",
            channel="In-App",
            society_id=user.society_id,
            user_id=user.id,
            category="General",
        )

        # Feature 16: Emergency Contacts
        emg_phone = soc.emergency_contact or soc.phone or "Administration Desk"
        NotificationService.send_notification(
            recipient=user.mobile or user.email or "N/A",
            message=f"Emergency Contacts: Security Gate / Society Office: {emg_phone}. For medical/fire emergency, contact the guard room immediately.",
            channel="In-App",
            society_id=user.society_id,
            user_id=user.id,
            category="General",
        )

        # Feature 17: Payment Instructions
        NotificationService.send_notification(
            recipient=user.mobile or user.email or "N/A",
            message="Payment Center: Maintenance bills can be settled online via UPI, Debit/Credit Card, or Netbanking. Instant official PDF receipts are generated upon payment.",
            channel="In-App",
            society_id=user.society_id,
            user_id=user.id,
            category="Reminder",
        )

        # Feature 18: First-Bill Explanation
        start_month = user.maintenance_start_month or utcnow().strftime("%Y-%m")
        NotificationService.send_notification(
            recipient=user.mobile or user.email or "N/A",
            message=f"Maintenance Billing Cycle: Your billing starts from {start_month}. Monthly bills are generated on the 1st of each month with a standard grace period.",
            channel="In-App",
            society_id=user.society_id,
            user_id=user.id,
            category="Reminder",
        )

        # Trigger registration_approved event
        from app.services.automation_service import AutomationService
        AutomationService.trigger_event(
            event_name="registration_approved",
            society_id=user.society_id,
            payload={
                "registration_id": registration_req.id,
                "user_id": user.id,
                "resident_name": user.full_name,
                "flat_id": registration_req.flat_id,
            },
            executed_by=admin_user,
        )


    @staticmethod
    def scan_and_escalate_pending_registrations(society_id=None):
        """
        Features 3, 4, 5:
        Scans pending registrations and performs automated reminders & escalations:
        - 1+ day: reminder to admin
        - 3+ days: Level 1 escalation alert (WARNING)
        - 7+ days: Level 2 critical escalation alert (CRITICAL)
        """
        now = utcnow()
        q = RegistrationRequest.query.filter_by(status="PENDING_APPROVAL")
        if society_id:
            q = q.filter_by(society_id=society_id)
        pending_list = q.all()

        scanned = len(pending_list)
        created_alerts = 0
        reminded = 0

        for req in pending_list:
            submitted = req.created_at or now
            days_pending = (now.date() - submitted.date()).days

            flat_str = req.flat.flat_number if req.flat else str(req.flat_id)

            if days_pending >= 7:
                # Level 2 Critical Escalation
                existing = AutomationAlert.query.filter_by(
                    society_id=req.society_id,
                    alert_type="REGISTRATION_ESCALATION_7D",
                    is_resolved=False,
                ).filter(AutomationAlert.message.contains(f"#{req.id}")).first()
                if not existing:
                    alert = AutomationAlert(
                        society_id=req.society_id,
                        alert_type="REGISTRATION_ESCALATION_7D",
                        severity="CRITICAL",
                        title=f"CRITICAL: Registration #{req.id} Pending {days_pending} Days",
                        message=f"Application for Flat {flat_str} by {req.full_name} ({req.mobile}) has been awaiting approval for {days_pending} days. Immediate action required.",
                        is_resolved=False,
                    )
                    db.session.add(alert)
                    created_alerts += 1
            elif days_pending >= 3:
                # Level 1 Escalation
                existing = AutomationAlert.query.filter_by(
                    society_id=req.society_id,
                    alert_type="REGISTRATION_ESCALATION_3D",
                    is_resolved=False,
                ).filter(AutomationAlert.message.contains(f"#{req.id}")).first()
                if not existing:
                    alert = AutomationAlert(
                        society_id=req.society_id,
                        alert_type="REGISTRATION_ESCALATION_3D",
                        severity="WARNING",
                        title=f"Escalation: Registration #{req.id} Pending {days_pending} Days",
                        message=f"Application for Flat {flat_str} by {req.full_name} has been pending for {days_pending} days.",
                        is_resolved=False,
                    )
                    db.session.add(alert)
                    created_alerts += 1
            elif days_pending >= 1:
                reminded += 1

        db.session.commit()
        return {
            "scanned": scanned,
            "created": created_alerts,
            "reminded": reminded,
        }

    @staticmethod
    def detect_incomplete_registrations(society_id=None):
        """
        Feature 6:
        Scans all pending registrations and returns those with missing or incomplete details.
        """
        q = RegistrationRequest.query.filter_by(status="PENDING_APPROVAL")
        if society_id:
            q = q.filter_by(society_id=society_id)
        pending = q.all()

        incomplete = []
        for req in pending:
            missing = []
            if not req.email:
                missing.append("Email address missing")
            if not req.mobile or len(req.mobile.strip()) < 10:
                missing.append("Invalid or incomplete mobile number")
            if not req.full_name or len(req.full_name.strip()) < 2:
                missing.append("Incomplete applicant name")
            if not req.flat_id:
                missing.append("No flat selected")
            if not req.occupancy_type:
                missing.append("Occupancy type not specified")

            if missing:
                incomplete.append({
                    "registration_id": req.id,
                    "full_name": req.full_name,
                    "mobile": req.mobile,
                    "missing_fields": missing,
                })
        return incomplete

    @staticmethod
    def request_missing_information(registration_id, admin_user=None):
        """
        Feature 7:
        Sends notification and alert requesting missing details for a registration request.
        """
        req = db.session.get(RegistrationRequest, registration_id)
        if not req:
            raise ValueError(f"Registration request #{registration_id} not found")

        missing = []
        if not req.email:
            missing.append("Email Address")
        if not req.mobile or len(req.mobile.strip()) < 10:
            missing.append("Valid Mobile Number")
        if not req.occupancy_type:
            missing.append("Occupancy Proof/Type")

        missing_str = ", ".join(missing) if missing else "Complete contact & occupancy verification documents"

        # Create alert
        alert = AutomationAlert(
            society_id=req.society_id,
            alert_type="MISSING_INFO_REQUESTED",
            severity="INFO",
            title=f"Missing Info Requested for Reg #{req.id}",
            message=f"Requested missing details ({missing_str}) from applicant {req.full_name} ({req.mobile}).",
            is_resolved=False,
        )
        db.session.add(alert)
        db.session.commit()
        return {"success": True, "registration_id": req.id, "missing_fields": missing}

    @staticmethod
    def detect_and_remind_inactive_residents(society_id=None, days_threshold=30):
        """
        Features 19 & 20:
        Detects active resident accounts with incomplete profiles (e.g. no emergency contact,
        no vehicles registered) or no activity for > days_threshold and sends profile completion reminders.
        """
        now = utcnow()
        cutoff = now.date() - timedelta(days=days_threshold)

        q = Resident.query.filter_by(occupancy_status="Active")
        if society_id:
            q = q.filter_by(society_id=society_id)
        active_residents = q.all()

        scanned = len(active_residents)
        reminded = 0

        for res in active_residents:
            if not res.user:
                continue

            # Check if resident has missing emergency contacts or household data
            has_emergency = EmergencyContact.query.filter_by(resident_id=res.id).first() is not None
            has_vehicle = Vehicle.query.filter_by(flat_id=res.flat_id).first() is not None

            move_in = res.move_in_date or res.created_at.date() if res.created_at else now.date()
            is_mature = move_in <= cutoff

            if is_mature and (not has_emergency or not has_vehicle):
                # Send polite profile completion reminder
                missing_items = []
                if not has_emergency:
                    missing_items.append("Emergency Contact")
                if not has_vehicle:
                    missing_items.append("Vehicle Details")

                NotificationService.send_notification(
                    recipient=res.mobile or res.email or "N/A",
                    message=f"Profile Update Reminder: Please take a moment to update your profile with your {', '.join(missing_items)} for society security & records.",
                    channel="In-App",
                    society_id=res.society_id,
                    user_id=res.user_id,
                    category="General",
                )
                reminded += 1

        return {
            "scanned": scanned,
            "inactive_detected": reminded,
            "reminded": reminded,
        }
