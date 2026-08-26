from app.models import (
    db,
    WorkOrder,
    Staff,
    Vendor,
    AutomationAlert,
)
from app.utils import utcnow
from datetime import timedelta
import secrets


class OperationsAutomationService:
    """
    Implements Phase 6 Society Operations Automation (Features 81–100):
    81. Daily operations checklist
    82. Weekly operations checklist
    83. Monthly operations checklist
    84. Automatic maintenance-task assignment
    85. Overdue-task detection
    86. Overdue-task escalation
    87. Staff reminder
    88. Recurring maintenance task
    89. Lift maintenance task
    90. Generator maintenance task
    91. Fire-safety inspection task
    92. CCTV inspection task
    93. Electrical inspection task
    94. Water-system inspection task
    95. Housekeeping inspection
    96. Security inspection
    97. Pest-control task
    98. Plumbing inspection
    99. Common-area inspection
    100. Daily operations report
    """

    @staticmethod
    def get_operations_checklist(society_id, frequency="daily"):
        """
        Features 81, 82, 83:
        Generates structured daily, weekly, or monthly operational checklist with execution status.
        """
        now = utcnow().date()
        checklists = {
            "daily": [
                {"id": "d_1", "task": "Security Guard Post Attendance & Shift Handover", "category": "Security", "responsible": "Security Guard"},
                {"id": "d_2", "task": "Water Tank Levels & Hydro-Pneumatic Pump Check", "category": "Water", "responsible": "Plumber"},
                {"id": "d_3", "task": "Clubhouse & Common Corridor Waste Collection", "category": "Housekeeping", "responsible": "Cleaner"},
                {"id": "d_4", "task": "Main Entrance Gate Visitor Log Verification", "category": "Security", "responsible": "Security Guard"},
                {"id": "d_5", "task": "Elevator Operational & Emergency Alarm Verification", "category": "Lift", "responsible": "Technician"},
            ],
            "weekly": [
                {"id": "w_1", "task": "Diesel Generator Battery & Fuel Level Check", "category": "Generator", "responsible": "Electrician"},
                {"id": "w_2", "task": "CCTV NVR Recording Status & Camera Lens Cleaning", "category": "CCTV", "responsible": "Technician"},
                {"id": "w_3", "task": "Fire Extinguisher Pressure Gauge Audit", "category": "Fire Safety", "responsible": "Safety Officer"},
                {"id": "w_4", "task": "Garden Sprinklers & Common Area Illumination Audit", "category": "Electrical", "responsible": "Gardener/Electrician"},
            ],
            "monthly": [
                {"id": "m_1", "task": "Monthly Elevator AMC Service & Safety Brake Inspection", "category": "Lift AMC", "responsible": "Elevator Vendor"},
                {"id": "m_2", "task": "Comprehensive Pest Control Fogging in Basements", "category": "Pest Control", "responsible": "Pest Control Vendor"},
                {"id": "m_3", "task": "Overhead & Underground Water Tank Chlorination", "category": "Water", "responsible": "Plumbing Contractor"},
                {"id": "m_4", "task": "Fire Hydrant Pump Flow & Smoke Detector Functional Test", "category": "Fire Safety", "responsible": "Fire AMC Vendor"},
            ]
        }
        return {
            "society_id": society_id,
            "frequency": frequency,
            "date": now.strftime("%Y-%m-%d"),
            "items": checklists.get(frequency.lower(), checklists["daily"]),
        }

    @staticmethod
    def auto_assign_maintenance_task(society_id, title, description, category, priority="Medium", due_days=2):
        """
        Feature 84:
        Automatically assigns maintenance task/work-order to available staff or vendor by role/category.
        """
        staff = Staff.query.filter_by(society_id=society_id, status="Active").filter(
            (Staff.role_type.ilike(f"%{category}%")) | (Staff.role_type.ilike("%Technician%"))
        ).first()

        vendor = None
        if not staff:
            vendor = Vendor.query.filter_by(society_id=society_id, status="Active").filter(
                Vendor.category.ilike(f"%{category}%")
            ).first()

        wo_num = f"WO-{society_id}-{secrets.token_hex(3).upper()}"
        due_date = utcnow().date() + timedelta(days=due_days)

        wo = WorkOrder(
            work_order_number=wo_num,
            society_id=society_id,
            title=title,
            description=description,
            category=category,
            priority=priority,
            assigned_staff_id=staff.id if staff else None,
            assigned_vendor_id=vendor.id if vendor else None,
            status="Assigned" if (staff or vendor) else "Created",
            due_date=due_date,
        )
        db.session.add(wo)
        db.session.commit()
        return wo


    @staticmethod
    def detect_and_escalate_overdue_tasks(society_id):
        """
        Features 85, 86, 87:
        Detects overdue work orders, escalates critical overdue items, and creates staff reminders.
        """
        now = utcnow().date()
        overdue_orders = WorkOrder.query.filter(
            WorkOrder.society_id == society_id,
            WorkOrder.due_date < now,
            WorkOrder.status.in_(["Created", "Assigned", "Accepted", "In Progress"]),
        ).all()

        escalations = 0
        for wo in overdue_orders:
            days_over = (now - wo.due_date).days
            severity = "CRITICAL" if (days_over > 3 or wo.priority in ["High", "Emergency"]) else "WARNING"

            existing = AutomationAlert.query.filter_by(
                society_id=society_id,
                alert_type="WORK_ORDER_OVERDUE",
                is_resolved=False,
            ).filter(AutomationAlert.message.contains(f"#{wo.work_order_number}")).first()

            if not existing:
                alert = AutomationAlert(
                    society_id=society_id,
                    alert_type="WORK_ORDER_OVERDUE",
                    severity=severity,
                    title=f"Overdue Work Order #{wo.work_order_number}",
                    message=f"Work order '{wo.title}' ({wo.category}) is {days_over} day(s) past due date ({wo.due_date}). Responsible: Staff #{wo.assigned_staff_id or 'Unassigned'}.",
                    is_resolved=False,
                )
                db.session.add(alert)
                escalations += 1

        db.session.commit()
        return {
            "overdue_tasks_count": len(overdue_orders),
            "escalations_created": escalations,
            "tasks": [{"id": wo.id, "number": wo.work_order_number, "title": wo.title, "days_overdue": (now - wo.due_date).days} for wo in overdue_orders]
        }

    @staticmethod
    def create_recurring_inspection_task(society_id, inspection_type):
        """
        Features 88–99:
        Creates recurring inspection tasks for:
        - Lift (89), Generator (90), Fire Safety (91), CCTV (92), Electrical (93),
        - Water System (94), Housekeeping (95), Security (96), Pest Control (97),
        - Plumbing (98), Common Area (99).
        """
        inspection_configs = {
            "lift": ("Elevator Safety & Brake Inspection", "Lift", "Emergency", 1),
            "generator": ("Diesel Generator Load Test & Fuel Audit", "Generator", "High", 7),
            "fire_safety": ("Fire Extinguisher & Smoke Detector Audit", "Fire Safety", "High", 14),
            "cctv": ("CCTV Cameras & Storage Health Check", "CCTV", "Medium", 7),
            "electrical": ("Main Distribution Panel & Lighting Audit", "Electrical", "Medium", 7),
            "water_system": ("Water Pump Flow & Overhead Tank Level Inspection", "Water", "High", 3),
            "housekeeping": ("Common Corridor & Stairwell Housekeeping Audit", "Housekeeping", "Low", 1),
            "security": ("Security Guard Gate Log & Perimeter Night Patrol Audit", "Security", "High", 1),
            "pest_control": ("Quarterly Basement Pest Control & Fogging Task", "Pest Control", "Medium", 30),
            "plumbing": ("Common Drainage & Valve Leakage Inspection", "Plumbing", "Medium", 7),
            "common_area": ("Clubhouse, Gym, and Podium Common Area Inspection", "Common Area", "Low", 7),
        }

        cfg = inspection_configs.get(inspection_type.lower(), ("General Facility Inspection", "Maintenance", "Medium", 7))
        title, category, priority, due_days = cfg
        return OperationsAutomationService.auto_assign_maintenance_task(
            society_id=society_id,
            title=title,
            description=f"Scheduled recurring operational maintenance task for {category}.",
            category=category,
            priority=priority,
            due_days=due_days,
        )

    @staticmethod
    def generate_daily_operations_report(society_id):
        """
        Feature 100:
        Generates daily consolidated operational status report.
        """
        checklist = OperationsAutomationService.get_operations_checklist(society_id, "daily")
        overdue = OperationsAutomationService.detect_and_escalate_overdue_tasks(society_id)
        open_orders = WorkOrder.query.filter_by(society_id=society_id).filter(WorkOrder.status != "Completed").count()
        active_staff = Staff.query.filter_by(society_id=society_id, status="Active").count()

        return {
            "society_id": society_id,
            "date": utcnow().strftime("%Y-%m-%d"),
            "daily_checklist_items": len(checklist["items"]),
            "open_work_orders": open_orders,
            "overdue_work_orders": overdue["overdue_tasks_count"],
            "active_staff_count": active_staff,
            "status": "Healthy" if overdue["overdue_tasks_count"] == 0 else "Attention Required",
        }
