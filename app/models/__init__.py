from app.models.tenant import db, Society, Building, Block, Flat
from app.models.user import User, Role, UserSession, OTPLog, AuditLog
from app.models.registration_request import RegistrationRequest
from app.models.resident import Resident, EmergencyContact, Dependent
from app.models.billing import MaintenanceConfig, MaintenanceBill, BillLineItem
from app.models.payment import Payment, PaymentReceipt, WebhookLog
from app.models.complaint import Complaint, ComplaintCategory, ComplaintComment
from app.models.visitor import Visitor, PreApprovedPass
from app.models.parking import ParkingSlot, Vehicle
from app.models.facility import Facility, FacilityBooking
from app.models.operations import (
    Staff,
    Vendor,
    WorkOrder,
    Asset,
    InventoryItem,
    InventoryTransaction,
)
from app.models.accounting import ExpenseVoucher, AccountLedger, FinancialYear
from app.models.communication import Notice, SocietyMeeting, PollVote, EmergencyAlert
from app.models.document import Document, DocumentCategory, DocumentAccessLog
from app.models.system import BackupLog, NotificationLog, SystemSetting
from app.models.support import SupportRequest
from app.models.notification_preference import NotificationPreference

__all__ = [
    "db",
    "Society",
    "Building",
    "Block",
    "Flat",
    "User",
    "Role",
    "UserSession",
    "OTPLog",
    "AuditLog",
    "RegistrationRequest",
    "Resident",
    "EmergencyContact",
    "Dependent",
    "MaintenanceConfig",
    "MaintenanceBill",
    "BillLineItem",
    "Payment",
    "PaymentReceipt",
    "WebhookLog",
    "Complaint",
    "ComplaintCategory",
    "ComplaintComment",
    "Visitor",
    "PreApprovedPass",
    "ParkingSlot",
    "Vehicle",
    "Facility",
    "FacilityBooking",
    "Staff",
    "Vendor",
    "WorkOrder",
    "Asset",
    "InventoryItem",
    "InventoryTransaction",
    "ExpenseVoucher",
    "AccountLedger",
    "FinancialYear",
    "Notice",
    "SocietyMeeting",
    "PollVote",
    "EmergencyAlert",
    "Document",
    "DocumentCategory",
    "DocumentAccessLog",
    "BackupLog",
    "NotificationLog",
    "SystemSetting",
    "SupportRequest",
    "NotificationPreference",
]
