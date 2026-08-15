import shutil
from app.models import db, Society, User


class HealthService:
    @staticmethod
    def get_system_health():
        """Performs health check on application, DB connection, and disk storage."""
        db_status = "Healthy"
        try:
            db.session.execute(db.select(1)).first()
        except Exception as e:
            db_status = f"Unhealthy: {str(e)}"

        total, used, free = shutil.disk_usage(".")
        disk_free_mb = free // (1024 * 1024)

        return {
            "status": "OK" if db_status == "Healthy" else "DEGRADED",
            "database": db_status,
            "disk_free_mb": disk_free_mb,
            "societies_count": Society.query.count(),
            "users_count": User.query.count(),
        }
