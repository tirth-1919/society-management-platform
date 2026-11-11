"""
AI Operations Database Models
=============================
Standardized data models for Society AI Intelligence Platform:
- AIFinding: Structured AI findings across all 13 intelligence subsystems
- AIAnalysisRun: Telemetry and execution records for scheduled/manual AI runs
- AIModelVersion: Model tracking, accuracy metrics, and active states
- AIInvestigation: Admin fraud & anomaly investigation workspace cases
- AIDocumentAnalysis: OCR field extraction and document verification records
- AIDuplicateCandidate: Identity and record duplicate candidate resolution
- AIEnergyReading: Common-area and equipment energy consumption logs
- AIParkingEvent: Parking violation and occupancy tracking records
- AIFindingFeedback: Admin decision records and evaluation feedback
"""

from __future__ import annotations

import json
from app.models.tenant import db
from app.utils import utcnow


class AIFindingSeverity:
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    ALL = [LOW, MEDIUM, HIGH, CRITICAL]


class AIFindingStatus:
    NEW = "NEW"
    REVIEWING = "REVIEWING"
    CONFIRMED = "CONFIRMED"
    DISMISSED = "DISMISSED"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    RESOLVED = "RESOLVED"
    ALL = [NEW, REVIEWING, CONFIRMED, DISMISSED, ACTION_REQUIRED, RESOLVED]


class AISystemType:
    OPERATIONS = "OPERATIONS"
    MAINTENANCE = "MAINTENANCE"
    SECURITY = "SECURITY"
    FINANCE = "FINANCE"
    INVOICE = "INVOICE"
    INCIDENT = "INCIDENT"
    ENERGY = "ENERGY"
    PARKING = "PARKING"
    COMPLAINTS = "COMPLAINTS"
    DOCUMENTS = "DOCUMENTS"
    DUPLICATES = "DUPLICATES"
    FRAUD = "FRAUD"
    DIGITAL_TWIN = "DIGITAL_TWIN"


class AIFinding(db.Model):
    __tablename__ = "ai_findings"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    ai_system = db.Column(
        db.String(50), nullable=False, index=True
    )  # AISystemType
    entity_type = db.Column(
        db.String(50), nullable=False, index=True
    )  # ASSET, PAYMENT, INVOICE, COMPLAINT, VISITOR, VEHICLE, DOCUMENT, RESIDENT, ENERGY_METER, GENERAL
    entity_id = db.Column(db.Integer, nullable=True, index=True)
    finding_type = db.Column(
        db.String(100), nullable=False, index=True
    )
    severity = db.Column(
        db.String(20), default=AIFindingSeverity.MEDIUM, nullable=False, index=True
    )
    confidence_score = db.Column(db.Float, default=1.0, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    evidence_json = db.Column(db.Text, nullable=True)
    recommended_action = db.Column(db.Text, nullable=True)
    status = db.Column(
        db.String(30), default=AIFindingStatus.NEW, nullable=False, index=True
    )
    
    # Workflow & Review tracking
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True
    )
    resolved_at = db.Column(db.DateTime, nullable=True)
    action_taken = db.Column(db.Text, nullable=True)
    investigation_id = db.Column(
        db.Integer, db.ForeignKey("ai_investigations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    metadata_json = db.Column(db.Text, nullable=True)

    # Relationships
    society = db.relationship("Society", foreign_keys=[society_id], lazy=True)
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id], lazy=True)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_evidence(self) -> dict | list:
        try:
            return json.loads(self.evidence_json or "{}")
        except Exception:
            return {}

    def set_evidence(self, data: dict | list) -> None:
        self.evidence_json = json.dumps(data, default=str)

    def get_metadata(self) -> dict:
        try:
            return json.loads(self.metadata_json or "{}")
        except Exception:
            return {}

    def set_metadata(self, data: dict) -> None:
        self.metadata_json = json.dumps(data, default=str)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "society_id": self.society_id,
            "ai_system": self.ai_system,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "finding_type": self.finding_type,
            "severity": self.severity,
            "confidence_score": round(self.confidence_score, 2),
            "confidence_percent": int(round(self.confidence_score * 100)),
            "title": self.title,
            "summary": self.summary,
            "evidence": self.get_evidence(),
            "recommended_action": self.recommended_action,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewed_by_id": self.reviewed_by_id,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "action_taken": self.action_taken,
            "investigation_id": self.investigation_id,
        }


class AIAnalysisRun(db.Model):
    __tablename__ = "ai_analysis_runs"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    ai_system = db.Column(db.String(50), nullable=False, index=True)
    triggered_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True
    )
    trigger_type = db.Column(db.String(30), default="SCHEDULED")  # SCHEDULED, MANUAL, EVENT
    status = db.Column(db.String(30), default="RUNNING")  # RUNNING, COMPLETED, FAILED
    findings_count = db.Column(db.Integer, default=0)
    summary = db.Column(db.Text, nullable=True)
    started_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    execution_time_ms = db.Column(db.Float, default=0.0)

    society = db.relationship("Society", foreign_keys=[society_id], lazy=True)
    triggered_by = db.relationship("User", foreign_keys=[triggered_by_id], lazy=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "society_id": self.society_id,
            "ai_system": self.ai_system,
            "trigger_type": self.trigger_type,
            "status": self.status,
            "findings_count": self.findings_count,
            "summary": self.summary,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_time_ms": self.execution_time_ms,
        }


class AIModelVersion(db.Model):
    __tablename__ = "ai_model_versions"

    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(100), nullable=False, index=True)
    model_version = db.Column(db.String(50), nullable=False)
    ai_system = db.Column(db.String(50), nullable=False, index=True)
    evaluation_date = db.Column(db.DateTime, nullable=True)
    data_period = db.Column(db.String(100), nullable=True)
    accuracy_metric = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(30), default="ACTIVE", index=True)  # ACTIVE, DEPRECATED, EVALUATION
    created_at = db.Column(db.DateTime, default=utcnow)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "ai_system": self.ai_system,
            "evaluation_date": self.evaluation_date.isoformat() if self.evaluation_date else None,
            "data_period": self.data_period,
            "accuracy_metric": self.accuracy_metric,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AIInvestigation(db.Model):
    __tablename__ = "ai_investigations"

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    title = db.Column(db.String(200), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    category = db.Column(
        db.String(50), default="GENERAL", index=True
    )  # FINANCIAL_FRAUD, ACCESS_ANOMALY, VENDOR_IRREGULARITY, GENERAL
    risk_score = db.Column(db.Float, default=50.0, nullable=False)
    severity = db.Column(
        db.String(20), default=AIFindingSeverity.HIGH, index=True
    )
    status = db.Column(
        db.String(30), default="OPEN", index=True
    )  # OPEN, UNDER_REVIEW, CONFIRMED, DISMISSED, RESOLVED
    
    assigned_to_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True
    )
    created_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True
    )
    evidence_timeline_json = db.Column(db.Text, nullable=True)
    related_entities_json = db.Column(db.Text, nullable=True)
    admin_notes = db.Column(db.Text, nullable=True)
    outcome_notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    closed_at = db.Column(db.DateTime, nullable=True)

    society = db.relationship("Society", foreign_keys=[society_id], lazy=True)
    assigned_to = db.relationship("User", foreign_keys=[assigned_to_id], lazy=True)
    created_by = db.relationship("User", foreign_keys=[created_by_id], lazy=True)
    findings = db.relationship("AIFinding", backref="investigation", foreign_keys="AIFinding.investigation_id", lazy=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_timeline(self) -> list:
        try:
            return json.loads(self.evidence_timeline_json or "[]")
        except Exception:
            return []

    def set_timeline(self, events: list) -> None:
        self.evidence_timeline_json = json.dumps(events, default=str)

    def get_related_entities(self) -> dict:
        try:
            return json.loads(self.related_entities_json or "{}")
        except Exception:
            return {}

    def set_related_entities(self, entities: dict) -> None:
        self.related_entities_json = json.dumps(entities, default=str)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "case_id": self.case_id,
            "society_id": self.society_id,
            "title": self.title,
            "summary": self.summary,
            "category": self.category,
            "risk_score": round(self.risk_score, 1),
            "severity": self.severity,
            "status": self.status,
            "assigned_to_id": self.assigned_to_id,
            "assigned_to_name": self.assigned_to.full_name if self.assigned_to else None,
            "timeline": self.get_timeline(),
            "related_entities": self.get_related_entities(),
            "admin_notes": self.admin_notes,
            "outcome_notes": self.outcome_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
        }


class AIDocumentAnalysis(db.Model):
    __tablename__ = "ai_document_analyses"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    document_id = db.Column(
        db.Integer, db.ForeignKey("documents.id"), nullable=False, index=True
    )
    detected_category = db.Column(db.String(50), nullable=True)
    confidence_score = db.Column(db.Float, default=0.0)
    extracted_fields_json = db.Column(db.Text, nullable=True)
    field_confidences_json = db.Column(db.Text, nullable=True)
    expiry_date = db.Column(db.Date, nullable=True, index=True)
    is_expired = db.Column(db.Boolean, default=False)
    potential_issues_json = db.Column(db.Text, nullable=True)
    verification_status = db.Column(
        db.String(30), default="PENDING", index=True
    )  # PENDING, VERIFIED, REJECTED, EXPIRED
    verified_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True
    )
    verified_at = db.Column(db.DateTime, nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    document = db.relationship("Document", foreign_keys=[document_id], lazy=True)
    society = db.relationship("Society", foreign_keys=[society_id], lazy=True)
    verified_by = db.relationship("User", foreign_keys=[verified_by_id], lazy=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_extracted_fields(self) -> dict:
        try:
            return json.loads(self.extracted_fields_json or "{}")
        except Exception:
            return {}

    def set_extracted_fields(self, data: dict) -> None:
        self.extracted_fields_json = json.dumps(data, default=str)

    def get_field_confidences(self) -> dict:
        try:
            return json.loads(self.field_confidences_json or "{}")
        except Exception:
            return {}

    def set_field_confidences(self, data: dict) -> None:
        self.field_confidences_json = json.dumps(data, default=str)

    def get_potential_issues(self) -> list:
        try:
            return json.loads(self.potential_issues_json or "[]")
        except Exception:
            return []

    def set_potential_issues(self, data: list) -> None:
        self.potential_issues_json = json.dumps(data, default=str)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "society_id": self.society_id,
            "document_id": self.document_id,
            "detected_category": self.detected_category,
            "confidence_score": round(self.confidence_score, 2),
            "extracted_fields": self.get_extracted_fields(),
            "field_confidences": self.get_field_confidences(),
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "is_expired": self.is_expired,
            "potential_issues": self.get_potential_issues(),
            "verification_status": self.verification_status,
            "verified_by_id": self.verified_by_id,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "rejection_reason": self.rejection_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AIDuplicateCandidate(db.Model):
    __tablename__ = "ai_duplicate_candidates"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    entity_type = db.Column(
        db.String(50), nullable=False, index=True
    )  # RESIDENT, VEHICLE, VENDOR, DOCUMENT, FLAT
    primary_entity_id = db.Column(db.Integer, nullable=False, index=True)
    duplicate_entity_id = db.Column(db.Integer, nullable=False, index=True)
    match_confidence = db.Column(db.Float, default=0.0, nullable=False)
    reasons_json = db.Column(db.Text, nullable=True)
    status = db.Column(
        db.String(30), default="PENDING", index=True
    )  # PENDING, CONFIRMED_DUPLICATE, NOT_DUPLICATE, MERGED
    reviewed_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True
    )
    reviewed_at = db.Column(db.DateTime, nullable=True)
    action_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    society = db.relationship("Society", foreign_keys=[society_id], lazy=True)
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id], lazy=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_reasons(self) -> list:
        try:
            return json.loads(self.reasons_json or "[]")
        except Exception:
            return []

    def set_reasons(self, data: list) -> None:
        self.reasons_json = json.dumps(data, default=str)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "society_id": self.society_id,
            "entity_type": self.entity_type,
            "primary_entity_id": self.primary_entity_id,
            "duplicate_entity_id": self.duplicate_entity_id,
            "match_confidence": round(self.match_confidence, 2),
            "reasons": self.get_reasons(),
            "status": self.status,
            "reviewed_by_id": self.reviewed_by_id,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "action_notes": self.action_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AIEnergyReading(db.Model):
    __tablename__ = "ai_energy_readings"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    meter_name = db.Column(db.String(100), nullable=False)
    meter_type = db.Column(
        db.String(50), default="COMMON_AREA", index=True
    )  # COMMON_AREA, DIESEL_GENERATOR, WATER_PUMP, EV_CHARGER, SOLAR, ELEVATOR
    reading_date = db.Column(db.Date, nullable=False, index=True)
    units_kwh = db.Column(db.Float, nullable=False)
    peak_demand_kw = db.Column(db.Float, default=0.0)
    cost_amount = db.Column(db.Float, default=0.0)
    source = db.Column(db.String(30), default="MANUAL")  # MANUAL, IMPORT, SENSOR_ADAPTER
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    society = db.relationship("Society", foreign_keys=[society_id], lazy=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "society_id": self.society_id,
            "meter_name": self.meter_name,
            "meter_type": self.meter_type,
            "reading_date": self.reading_date.isoformat() if self.reading_date else None,
            "units_kwh": round(self.units_kwh, 2),
            "peak_demand_kw": round(self.peak_demand_kw, 2),
            "cost_amount": round(self.cost_amount, 2),
            "source": self.source,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AIParkingEvent(db.Model):
    __tablename__ = "ai_parking_events"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    slot_id = db.Column(
        db.Integer, db.ForeignKey("parking_slots.id"), nullable=True, index=True
    )
    vehicle_id = db.Column(
        db.Integer, db.ForeignKey("vehicles.id"), nullable=True, index=True
    )
    vehicle_number = db.Column(db.String(50), nullable=True, index=True)
    event_type = db.Column(
        db.String(50), nullable=False, index=True
    )  # UNAUTHORIZED_PARKING, OVERSTAY, WRONG_SLOT, VISITOR_IN_RESIDENT_SLOT, EV_SLOT_NON_EV, ABANDONED_SUSPECT
    occurred_at = db.Column(db.DateTime, default=utcnow, index=True)
    reported_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True
    )
    status = db.Column(
        db.String(30), default="DETECTED", index=True
    )  # DETECTED, CONFIRMED, DISMISSED, ACTIONED
    notes = db.Column(db.Text, nullable=True)

    society = db.relationship("Society", foreign_keys=[society_id], lazy=True)
    slot = db.relationship("ParkingSlot", foreign_keys=[slot_id], lazy=True)
    vehicle = db.relationship("Vehicle", foreign_keys=[vehicle_id], lazy=True)
    reported_by = db.relationship("User", foreign_keys=[reported_by_id], lazy=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "society_id": self.society_id,
            "slot_id": self.slot_id,
            "slot_number": self.slot.slot_number if self.slot else None,
            "vehicle_id": self.vehicle_id,
            "vehicle_number": self.vehicle_number,
            "event_type": self.event_type,
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
            "status": self.status,
            "notes": self.notes,
        }


class AIFindingFeedback(db.Model):
    __tablename__ = "ai_finding_feedbacks"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    finding_id = db.Column(
        db.Integer, db.ForeignKey("ai_findings.id"), nullable=False, index=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    decision = db.Column(
        db.String(50), nullable=False
    )  # CONFIRMED, DISMISSED, FALSE_POSITIVE, NOT_DUPLICATE, ACTION_TAKEN
    feedback_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    finding = db.relationship("AIFinding", foreign_keys=[finding_id], backref="feedbacks", lazy=True)
    user = db.relationship("User", foreign_keys=[user_id], lazy=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
