from flask import session, abort
from app.models import Role


class TenantService:
    @staticmethod
    def get_current_society_id():
        """Extracts society_id from user session."""
        return session.get("society_id")

    @staticmethod
    def enforce_tenant_isolation(user, requested_society_id):
        """
        Enforces tenant isolation rule:
        Super Admin can access any society.
        Society users can ONLY access their assigned society.
        If unauthorized cross-tenant attempt occurs, abort with 403 Forbidden.
        """
        if not user:
            abort(401, description="Authentication required")

        if user.role == Role.SUPER_ADMIN:
            return True

        if user.society_id != requested_society_id:
            abort(403, description="Forbidden: Cross-tenant access is not authorized")

        return True

    @staticmethod
    def filter_query_by_society(query, model_class, society_id):
        """Filters SQLAlchemy query by society_id if the model has a society_id field."""
        if hasattr(model_class, "society_id") and society_id:
            return query.filter(model_class.society_id == society_id)
        return query
