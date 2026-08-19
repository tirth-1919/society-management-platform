import os
import click
from flask import Flask, render_template
from flask_migrate import Migrate
from app.config import config
from app.models import db

migrate = Migrate()


def create_app(config_name=None):
    if not config_name:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config.get(config_name, config["default"]))

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Ensure instance directories exist
    os.makedirs(app.config["INSTANCE_DIR"], exist_ok=True)
    os.makedirs(app.config["BACKUP_DIR"], exist_ok=True)
    os.makedirs(app.config["DOCUMENT_STORAGE_DIR"], exist_ok=True)

    # Register blueprints
    from app.routes import (
        auth_bp,
        main_bp,
        admin_bp,
        payments_bp,
        complaints_bp,
        visitors_bp,
        facilities_bp,
        accounting_bp,
        operations_bp,
        documents_bp,
        system_bp,
        reports_bp,
        api_bp,
        resident_bp,
    )

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(complaints_bp)
    app.register_blueprint(visitors_bp)
    app.register_blueprint(facilities_bp)
    app.register_blueprint(accounting_bp)
    app.register_blueprint(operations_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(resident_bp)

    # Supports existing SQLite installations until Alembic migrations are run.
    from app.models.tenant import patch_sqlite_schema

    with app.app_context():
        patch_sqlite_schema(app)

    @app.cli.command("send-maintenance-notifications")
    @click.option("--society-id", type=int, default=None)
    def send_maintenance_notifications(society_id):
        """Dispatch the billing-cycle upcoming and overdue SMS notifications."""
        from app.services.notification_service import NotificationService

        sent = NotificationService.send_maintenance_reminders(society_id=society_id)
        click.echo(f"Sent {len(sent)} maintenance notifications.")

<<<<<<< HEAD
    @app.cli.command("generate-monthly-bills")
    @click.option("--society-id", type=int, required=True)
    @click.option("--month", type=str, default=None)
    def generate_monthly_bills_cmd(society_id, month):
        """Generate monthly maintenance bills for all active flats in a society."""
        from app.services.billing_service import BillingService

        bills = BillingService.generate_monthly_bills(society_id=society_id, billing_month=month)
        click.echo(f"Generated {len(bills)} maintenance bills for society #{society_id}.")

    @app.cli.command("apply-late-fees")
    @click.option("--society-id", type=int, default=None)
    def apply_late_fees_cmd(society_id):
        """Apply late fees to overdue maintenance bills."""
        from app.services.billing_service import BillingService

        updated = BillingService.apply_due_late_fees(society_id=society_id)
        click.echo(f"Applied late fees to {len(updated)} overdue bills.")

    @app.cli.command("expire-visitor-passes")
    def expire_visitor_passes_cmd():
        """Expire outdated visitor passes past validity period."""
        from app.models import PreApprovedPass, db
        from app.utils import utcnow

        passes = PreApprovedPass.query.filter(
            PreApprovedPass.is_used == False,
            PreApprovedPass.expected_date < utcnow().date(),
        ).all()
        for p in passes:
            p.is_used = True
        db.session.commit()
        click.echo(f"Expired {len(passes)} visitor passes.")

    @app.cli.command("backup-database")
    def backup_database_cmd():
        """Trigger automated database backup."""
        from app.services.backup_service import BackupService

        b = BackupService.create_database_backup()
        click.echo(f"Database backup created: {b.filename} ({b.file_size_bytes} bytes).")

    @app.cli.command("repair-receipts")
    def repair_receipts_cmd():
        """Audit and repair missing or stale payment receipt PDFs."""
        from app.models import PaymentReceipt
        from app.services.receipt_service import ReceiptService

        receipts = PaymentReceipt.query.all()
        repaired = 0
        for r in receipts:
            try:
                ReceiptService.generate_pdf_receipt(r.payment_id)
                repaired += 1
            except Exception as e:
                click.echo(f"Failed receipt {r.id}: {e}")
        click.echo(f"Audited and verified {repaired} payment receipts.")

    @app.cli.command("run-daily-check")
    @click.option("--society-id", type=int, default=None)
    def run_daily_check_cmd(society_id):
        """Run daily automated society health audit."""
        from app.services.society_health_service import SocietyHealthService

        res = SocietyHealthService.run_full_society_audit(society_id=society_id)
        click.echo(f"Health Audit Status: {res['status']} (Score: {res['health_score']}/100 - {res['tier']})")

    @app.cli.command("reconcile-payments")
    @click.option("--society-id", type=int, default=None)
    def reconcile_payments_cmd(society_id):
        """Run 12-point payment reconciliation scan."""
        from app.services.reconciliation_service import PaymentReconciliationService

        res = PaymentReconciliationService.reconcile_all(society_id=society_id)
        click.echo(f"Scanned {res['records_scanned']} records. Created {res['records_created']} reconciliation issues.")

    @app.cli.command("run-automation")
    @click.argument("action_type")
    @click.option("--society-id", type=int, default=None)
    def run_automation_cmd(action_type, society_id):
        """Execute a registered automation action by name."""
        from app.services.automation_service import AutomationService

        res = AutomationService.execute_job(action_type=action_type, society_id=society_id, trigger_source="CLI")
        click.echo(f"Automation execution: {res['status']} (ID: {res.get('execution_id')})")

    # Security headers
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    # Custom error handlers
    @app.errorhandler(400)
    def bad_request(e):
        return render_template("errors/400.html", error=e), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return render_template("errors/401.html", error=e), 401

=======
    # Custom error handlers
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html", error=e), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html", error=e), 404

<<<<<<< HEAD
    @app.errorhandler(429)
    def too_many_requests(e):
        return render_template("errors/429.html", error=e), 429

=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template("errors/500.html", error=e), 500

    return app
