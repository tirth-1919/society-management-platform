from flask import Blueprint, jsonify, render_template, request, redirect, url_for, flash
from app.models import BackupLog, AuditLog
from app.services.health_service import HealthService
from app.services.backup_service import BackupService

system_bp = Blueprint("system", __name__)


@system_bp.route("/health")
def health():
    return jsonify(HealthService.get_system_health()), 200


@system_bp.route("/ready")
def ready():
    return jsonify({"readiness": "READY"}), 200


@system_bp.route("/system/backups", methods=["GET", "POST"])
def backups():
    if request.method == "POST":
        b = BackupService.create_database_backup()
        flash(
            f"Database backup archive '{b.filename}' created successfully!", "success"
        )
        return redirect(url_for("system.backups"))

    backups_list = BackupLog.query.order_by(BackupLog.created_at.desc()).all()
    audit_logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(30).all()
    health_metrics = HealthService.get_system_health()
    return render_template(
        "system/health.html",
        backups=backups_list,
        audit_logs=audit_logs,
        health=health_metrics,
    )
