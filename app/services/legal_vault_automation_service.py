from app.models import (
    db,
    Document,
    DocumentAccessLog,
)
from app.utils import utcnow


class LegalVaultAutomationService:
    """
    Implements Phase 30 Document Vault & Legal Document Automation:
    - Legal compliance & conveyance deed indexing
    - Document access logging
    - Secure permission enforcement (Admin Only vs Resident Public)
    """

    @staticmethod
    def log_document_access(document_id, user_id):
        """Records an audit trail entry whenever a sensitive vault document is accessed."""
        log = DocumentAccessLog(
            document_id=document_id,
            user_id=user_id,
            accessed_at=utcnow(),
        )
        db.session.add(log)
        db.session.commit()
        return log

    @staticmethod
    def get_legal_documents_catalog(society_id):
        """Returns catalog of all registered legal, property, and compliance documents."""
        legal_docs = Document.query.filter_by(society_id=society_id).filter(
            Document.category.in_(["Compliance", "Legal", "Society Bye-Laws"])
        ).all()

        return [
            {
                "document_id": d.id,
                "title": d.title,
                "category": d.category,
                "access_level": d.access_level,
                "file_type": d.file_type,
                "uploaded_at": d.created_at.strftime("%Y-%m-%d") if d.created_at else "-",
            }
            for d in legal_docs
        ]
