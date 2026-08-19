from app.routes.auth import auth_bp
from app.routes.main import main_bp
from app.routes.admin import admin_bp
from app.routes.payments import payments_bp
from app.routes.complaints import complaints_bp
from app.routes.visitors import visitors_bp
from app.routes.facilities import facilities_bp
from app.routes.accounting import accounting_bp
from app.routes.operations import operations_bp
from app.routes.documents import documents_bp
from app.routes.system_health import system_bp
from app.routes.reports import reports_bp
from app.routes.api import api_bp
from app.routes.resident import resident_bp

__all__ = [
    "auth_bp",
    "main_bp",
    "admin_bp",
    "payments_bp",
    "complaints_bp",
    "visitors_bp",
    "facilities_bp",
    "accounting_bp",
    "operations_bp",
    "documents_bp",
    "system_bp",
    "reports_bp",
    "api_bp",
    "resident_bp",
]
