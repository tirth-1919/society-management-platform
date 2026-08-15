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

    # Custom error handlers
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html", error=e), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html", error=e), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template("errors/500.html", error=e), 500

    return app
