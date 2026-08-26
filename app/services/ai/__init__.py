"""
AI Services Package
===================
Provides modular AI and smart productivity services for residents and society administrators.
Includes provider abstractions, recommendation engines, resident next actions, admin work queue,
contextual help, form assistants, communication intelligence, incident analysis, data quality audits,
health monitoring, feature usage telemetry, and audit diffing.
"""

from app.services.ai.provider import (
    AIProvider,
    DeterministicAIProvider,
    MockAIProvider,
    OpenAIProvider,
    GeminiProvider,
    AIProviderFactory,
)
from app.services.ai.recommendation_service import AIRecommendationService
from app.services.ai.resident_ai import ResidentNextActionService, SmartResidentStatusService
from app.services.ai.admin_ai import AdminWorkQueueService, AdminFocusModeService, SafeBulkActionGuard, RecordChangePreviewService
from app.services.ai.contextual_help_service import ContextualHelpService
from app.services.ai.form_assistant_service import FormAssistantService
from app.services.ai.communication_ai import CommunicationAIService
from app.services.ai.incident_ai import IncidentAIService
from app.services.ai.data_quality_ai import DataQualityAIService, DuplicateResidentDetector
from app.services.ai.csv_import_ai import CSVImportAIService
from app.services.ai.health_ai import HealthAIService
from app.services.ai.feature_usage_service import FeatureUsageService
from app.services.ai.what_changed_service import WhatChangedService
from app.services.ai.ai_audit_service import AIAuditService
from app.services.ai.ai_model_service import AIModelManagementService
from app.services.ai.predictive_maintenance_service import PredictiveMaintenanceAIService
from app.services.ai.security_command_service import SecurityCommandAIService, CCTVStreamAdapter, MockCCTVStreamAdapter
from app.services.ai.financial_control_service import FinancialControlAIService
from app.services.ai.invoice_processing_service import InvoiceProcessingAIService
from app.services.ai.incident_response_service import IncidentResponseAIService
from app.services.ai.energy_intelligence_service import EnergyIntelligenceAIService
from app.services.ai.parking_intelligence_service import ParkingIntelligenceAIService
from app.services.ai.complaint_intelligence_service import ComplaintIntelligenceAIService
from app.services.ai.document_verification_service import DocumentVerificationAIService
from app.services.ai.duplicate_resolution_service import DuplicateResolutionAIService
from app.services.ai.fraud_investigation_service import FraudInvestigationAIService
from app.services.ai.digital_twin_service import DigitalTwinAIService
from app.services.ai.ai_operations_service import AIOperationsService

__all__ = [
    "AIProvider",
    "DeterministicAIProvider",
    "MockAIProvider",
    "OpenAIProvider",
    "GeminiProvider",
    "AIProviderFactory",
    "AIRecommendationService",
    "ResidentNextActionService",
    "SmartResidentStatusService",
    "AdminWorkQueueService",
    "AdminFocusModeService",
    "SafeBulkActionGuard",
    "RecordChangePreviewService",
    "ContextualHelpService",
    "FormAssistantService",
    "CommunicationAIService",
    "IncidentAIService",
    "DataQualityAIService",
    "DuplicateResidentDetector",
    "CSVImportAIService",
    "HealthAIService",
    "FeatureUsageService",
    "WhatChangedService",
    "AIAuditService",
    "AIModelManagementService",
    "PredictiveMaintenanceAIService",
    "SecurityCommandAIService",
    "CCTVStreamAdapter",
    "MockCCTVStreamAdapter",
    "FinancialControlAIService",
    "InvoiceProcessingAIService",
    "IncidentResponseAIService",
    "EnergyIntelligenceAIService",
    "ParkingIntelligenceAIService",
    "ComplaintIntelligenceAIService",
    "DocumentVerificationAIService",
    "DuplicateResolutionAIService",
    "FraudInvestigationAIService",
    "DigitalTwinAIService",
    "AIOperationsService",
]
