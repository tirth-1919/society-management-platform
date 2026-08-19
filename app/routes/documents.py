import secrets
from pathlib import Path
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    send_file,
    abort,
)
from werkzeug.utils import secure_filename
from app.models import db, Document, User, Role
from app.services.tenant_service import TenantService

documents_bp = Blueprint("documents", __name__, url_prefix="/documents")


# Security fix: this blueprint previously had no authentication or
# authorization guard at all, and 'download' never checked society_id or
# access_level â€” any request could read any society's ADMIN_ONLY document
# by guessing an id. This vault remains an admin-only management surface;
# residents get their own read-only view via resident.documents below,
# which only ever returns RESIDENT_PUBLIC documents for their own society.
@documents_bp.before_request
def admin_only_guard():
    user_id = session.get("user_id")
    if not user_id:
        abort(403, description="Forbidden: authentication required")
    user = db.session.get(User, user_id)
    if (
        not user
        or user.account_status != "ACTIVE"
        or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]
    ):
        abort(403, description="Forbidden: admin access required")
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)


@documents_bp.route("/")
def vault():
    user = db.session.get(User, session.get("user_id"))
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)
    docs = Document.query.filter_by(society_id=society_id).all()
    return render_template("documents/vault.html", documents=docs)


@documents_bp.route("/upload", methods=["POST"])
def upload():
    user = db.session.get(User, session.get("user_id"))
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)
    user_id = user.id


    title = request.form.get("title")
    category = request.form.get("category", "General")
    access_level = request.form.get("access_level", "ADMIN_ONLY")
    if access_level not in ("ADMIN_ONLY", "RESIDENT_PUBLIC", "VENDOR_RESTRICTED"):
        access_level = "ADMIN_ONLY"
    file = request.files.get("file")

    if not file or not file.filename:
        flash("No file selected", "danger")
        return redirect(url_for("documents.vault"))

    # Only a small, safe set of document types is accepted â€” never
    # executables or scripts â€” and the stored filename is always
    # server-generated from a sanitized name, never trusted as a path.
    allowed_ext = {"pdf", "png", "jpg", "jpeg", "doc", "docx", "txt"}
    original_name = secure_filename(file.filename)
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if ext not in allowed_ext:
        flash("Unsupported file type. Allowed: PDF, image, DOC/DOCX, TXT.", "danger")
        return redirect(url_for("documents.vault"))

    save_dir = Path("instance/documents")
    save_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"doc_{society_id}_{secrets.token_hex(4)}_{secure_filename(title or 'file')}.{ext}"
    save_path = (save_dir / safe_name).resolve()
    # Defence in depth against path traversal even though secure_filename
    # already strips '../' and absolute-path components.
    if (
        save_dir.resolve() not in save_path.parents
        and save_path.parent != save_dir.resolve()
    ):
        abort(400, description="Invalid file path")
    file.save(save_path)

    doc = Document(
        society_id=society_id,
        title=title,
        category=category,
        file_path=str(save_path),
        file_size_bytes=save_path.stat().st_size,
        file_type=ext,
        uploaded_by_id=user_id,
        access_level=access_level,
    )
    db.session.add(doc)
    db.session.commit()
    flash(f"Document '{title}' uploaded securely to Vault!", "success")
    return redirect(url_for("documents.vault"))


@documents_bp.route("/download/<int:doc_id>")
def download(doc_id):
    user = db.session.get(User, session.get("user_id"))
    doc = Document.query.get_or_404(doc_id)
    TenantService.enforce_tenant_isolation(user, doc.society_id)
    p = Path(doc.file_path)
    if not p.exists():
        abort(404, description="Document file not found on server.")
    return send_file(str(p), as_attachment=True)

