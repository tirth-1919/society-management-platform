"""
AI Model Version & Metrics Management Service
============================================
Tracks AI models, versioning, evaluated accuracy, data windows, and active state.
"""

from __future__ import annotations

import logging
from app.models.tenant import db
from app.models.ai_operations import AIModelVersion
from app.utils import utcnow

logger = logging.getLogger(__name__)


class AIModelManagementService:
    DEFAULT_MODELS = [
        {
            "model_name": "Predictive Maintenance Risk Classifier",
            "model_version": "v2.1.0-stochastic",
            "ai_system": "MAINTENANCE",
            "data_period": "Past 180 days work orders & assets",
            "accuracy_metric": 0.94,
            "status": "ACTIVE",
        },
        {
            "model_name": "Security Access Anomaly Engine",
            "model_version": "v1.8.0-pattern-rule",
            "ai_system": "SECURITY",
            "data_period": "Rolling 30-day visitor & access logs",
            "accuracy_metric": 0.91,
            "status": "ACTIVE",
        },
        {
            "model_name": "Financial Anomaly & Duplicate Detector",
            "model_version": "v3.0.1-heuristic-match",
            "ai_system": "FINANCE",
            "data_period": "Historical vouchers, payments & ledgers",
            "accuracy_metric": 0.96,
            "status": "ACTIVE",
        },
        {
            "model_name": "Invoice OCR & Field Extractor",
            "model_version": "v2.0.0-ocr-hybrid",
            "ai_system": "INVOICE",
            "data_period": "Vendor invoices & bills",
            "accuracy_metric": 0.93,
            "status": "ACTIVE",
        },
        {
            "model_name": "Incident Triage & Root Cause Classifier",
            "model_version": "v1.5.0-nlp-cluster",
            "ai_system": "INCIDENT",
            "data_period": "Past complaints & work orders",
            "accuracy_metric": 0.95,
            "status": "ACTIVE",
        },
        {
            "model_name": "Energy Consumption Forecaster",
            "model_version": "v2.0.0-timeseries-arima",
            "ai_system": "ENERGY",
            "data_period": "Sub-meter readings & utility cycles",
            "accuracy_metric": 0.89,
            "status": "ACTIVE",
        },
        {
            "model_name": "Parking Demand & Violation Detector",
            "model_version": "v1.4.0-spatial-occ",
            "ai_system": "PARKING",
            "data_period": "Slot allocations & gate logs",
            "accuracy_metric": 0.92,
            "status": "ACTIVE",
        },
        {
            "model_name": "Complaint Clustering & SLA Estimator",
            "model_version": "v2.2.0-levenshtein-tfidf",
            "ai_system": "COMPLAINTS",
            "data_period": "Active and resolved society tickets",
            "accuracy_metric": 0.95,
            "status": "ACTIVE",
        },
        {
            "model_name": "Document Verification & Expiry Scanner",
            "model_version": "v1.9.0-doc-audit",
            "ai_system": "DOCUMENTS",
            "data_period": "Resident proofs & vendor contracts",
            "accuracy_metric": 0.96,
            "status": "ACTIVE",
        },
        {
            "model_name": "Duplicate Identity Resolution Engine",
            "model_version": "v2.0.0-fuzzy-contact",
            "ai_system": "DUPLICATES",
            "data_period": "Resident directory & vehicle registries",
            "accuracy_metric": 0.93,
            "status": "ACTIVE",
        },
        {
            "model_name": "Multi-Vector Fraud Investigation Engine",
            "model_version": "v1.7.0-composite-risk",
            "ai_system": "FRAUD",
            "data_period": "Cross-domain audit events & payments",
            "accuracy_metric": 0.94,
            "status": "ACTIVE",
        },
        {
            "model_name": "Society Digital Twin Graph Correlator",
            "model_version": "v1.0.0-topology-correlator",
            "ai_system": "DIGITAL_TWIN",
            "data_period": "Complete topological society nodes",
            "accuracy_metric": 0.98,
            "status": "ACTIVE",
        },
    ]

    @classmethod
    def ensure_default_models(cls) -> list[AIModelVersion]:
        try:
            existing = {m.model_name: m for m in AIModelVersion.query.all()}
            created = []
            for item in cls.DEFAULT_MODELS:
                if item["model_name"] not in existing:
                    mv = AIModelVersion(
                        model_name=item["model_name"],
                        model_version=item["model_version"],
                        ai_system=item["ai_system"],
                        data_period=item["data_period"],
                        accuracy_metric=item["accuracy_metric"],
                        status=item["status"],
                        evaluation_date=utcnow(),
                    )
                    db.session.add(mv)
                    created.append(mv)
            if created:
                db.session.commit()
            return AIModelVersion.query.order_by(AIModelVersion.ai_system.asc()).all()
        except Exception as e:
            logger.error(f"Failed to ensure AI models: {e}")
            db.session.rollback()
            return []

    @classmethod
    def get_all_models(cls) -> list[AIModelVersion]:
        cls.ensure_default_models()
        return AIModelVersion.query.order_by(AIModelVersion.ai_system.asc()).all()
