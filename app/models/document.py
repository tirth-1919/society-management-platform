from app.models.tenant import db
from app.utils import utcnow


class DocumentCategory(db.Model):
    __tablename__ = "document_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(
        db.String(50), unique=True, nullable=False
    )  # Resident Proofs, Vendor Contracts, Society Bye-Laws, Financial Receipts, Audit Reports


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    title = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    file_size_bytes = db.Column(db.Integer, default=0)
    file_type = db.Column(db.String(50), default="pdf")

    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    access_level = db.Column(
        db.String(30), default="ADMIN_ONLY"
    )  # ADMIN_ONLY, RESIDENT_PUBLIC, VENDOR_RESTRICTED
    created_at = db.Column(db.DateTime, default=utcnow)


class DocumentAccessLog(db.Model):
    __tablename__ = "document_access_logs"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(
        db.Integer, db.ForeignKey("documents.id"), nullable=False, index=True
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    accessed_at = db.Column(db.DateTime, default=utcnow)



