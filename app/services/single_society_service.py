# Resolve the configured society for the single-society application."

from flask import current_app
from app.models import Society
class SingleSocietyService:
    @staticmethod
    def get_id():
        # Return the configured existing society ID, or fail safely.
        configured = current_app.config.get("SINGLE_SOCIETY_ID")
        if configured in (None, ""):
            society = Society.query.filter(Society.name.ilike("Sunrise Heights")).first()
            if society:
                return society.id
            societies = Society.query.order_by(Society.id).all()
            if len(societies) == 1:
                return societies[0].id
            raise RuntimeError("SINGLE_SOCIETY_ID must be configured for a multi-society database")
        try:
            society_id = int(configured)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("SINGLE_SOCIETY_ID must be an integer") from exc
        if not Society.query.filter_by(id=society_id).first():
            raise RuntimeError("Configured SINGLE_SOCIETY_ID does not exist")
        return society_id
