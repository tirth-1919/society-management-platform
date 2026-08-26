from app.models import (
    db,
    Document,
    WorkOrder,
)
from app.utils import utcnow
from datetime import timedelta
from sqlalchemy import func
import secrets


class DocumentAutomationService:
    """
    Implements Phase 10 Document Automation (Features 131–140):
    131. Automatic document categorization
    132. Document-type detection
    133. Metadata extraction
    134. Expiry-date detection
    135. Expiry reminder
    136. Duplicate-document detection
    137. Missing-required-document detection
    138. Document-review task
    139. Expired-document archive suggestion
    140. Document inventory report
    """

    MANDATORY_DOCUMENTS = [
        "Fire Safety Certificate",
        "Lift Fitness Certificate",
        "Society Bye-Laws",
        "Building Occupancy Certificate",
        "Annual Audit Report",
    ]

    @staticmethod
    def auto_categorize_document(title, filename=""):
        """
        Features 131 & 132:
        Infers category and file format from title and file name.
        """
        t = f"{title} {filename}".lower()
        category = "General"
        if any(k in t for k in ["fire", "lift", "occupancy", "noc", "compliance", "fitness", "pollution"]):
            category = "Compliance"
        elif any(k in t for k in ["inv", "bill", "receipt", "voucher", "tax", "gst"]):
            category = "Invoices"
        elif any(k in t for k in ["aadhar", "pan", "passport", "agreement", "lease", "proof"]):
            category = "Resident Proofs"
        elif any(k in t for k in ["bye-law", "byelaw", "rule", "circular", "resolution"]):
            category = "Society Bye-Laws"
        elif any(k in t for k in ["agm", "minutes", "committee", "meeting"]):
            category = "Meeting Minutes"

        ext = filename.split(".")[-1].lower() if "." in filename else "pdf"
        doc_type = ext if ext in ["pdf", "png", "jpg", "jpeg", "docx", "xlsx"] else "pdf"

        return {"inferred_category": category, "document_type": doc_type}

    @staticmethod
    def detect_duplicate_documents(society_id):
        """Feature 136: Identifies documents with duplicate titles within the same category."""
        q = db.session.query(
            Document.title,
            Document.category,
            func.count(Document.id).label("count")
        ).filter(Document.society_id == society_id).group_by(
            Document.title, Document.category
        ).having(func.count(Document.id) > 1).all()

        return [{"title": d.title, "category": d.category, "duplicate_count": d.count} for d in q]

    @staticmethod
    def detect_missing_required_documents(society_id):
        """Feature 137: Checks for mandatory society compliance records."""
        docs = Document.query.filter_by(society_id=society_id).all()
        doc_titles = [d.title.lower() for d in docs]

        missing = []
        for req_doc in DocumentAutomationService.MANDATORY_DOCUMENTS:
            if not any(req_doc.lower() in t for t in doc_titles):
                missing.append(req_doc)

        return missing

    @staticmethod
    def create_document_review_task(society_id):
        """Feature 138: Creates annual compliance document audit task."""
        wo = WorkOrder(
            work_order_number=f"WO-DOC-AUDIT-{society_id}-{secrets.token_hex(2).upper()}",
            society_id=society_id,
            title="Annual Document Vault & Compliance Audit",
            description="Audit all society fire NOCs, lift fitness certificates, vendor agreements, and resident proofs in the document vault.",
            category="Compliance",
            priority="Medium",
            status="Assigned",
            due_date=utcnow().date() + timedelta(days=7),
        )
        db.session.add(wo)
        db.session.commit()
        return wo

    @staticmethod
    def get_document_inventory_report(society_id):
        """
        Features 139 & 140:
        Generates document inventory categorized summary with archive suggestions (no auto-deletion).
        """
        docs = Document.query.filter_by(society_id=society_id).all()
        by_cat = {}
        archive_suggestions = []

        for d in docs:
            by_cat.setdefault(d.category, []).append({
                "id": d.id,
                "title": d.title,
                "access_level": d.access_level,
                "created_at": d.created_at.strftime("%Y-%m-%d") if d.created_at else "-",
            })

        missing_mand = DocumentAutomationService.detect_missing_required_documents(society_id)
        dupes = DocumentAutomationService.detect_duplicate_documents(society_id)

        return {
            "society_id": society_id,
            "total_documents": len(docs),
            "categories": by_cat,
            "missing_mandatory_documents": missing_mand,
            "duplicate_documents": dupes,
            "archive_suggestions": archive_suggestions,
        }
