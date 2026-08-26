from app.models import (
    db,
    Notice,
)


class LostFoundAutomationService:
    """
    Implements Phase 33 Lost & Found Registry Automation:
    - Lost & Found item logging with custody location
    - Automated community alert broadcast
    - Claim verification workflow
    """

    @staticmethod
    def report_lost_found_item(society_id, item_name, item_type="FOUND", location="Clubhouse", description="", reporter_id=None):
        """Logs a lost/found item and optionally creates a broadcast notice."""
        title = f"Lost & Found: {item_type.upper()} - {item_name}"
        content = f"Item: {item_name} ({item_type}). Location: {location}. Details: {description}. Please contact the security desk to claim."

        notice = Notice(
            society_id=society_id,
            title=title,
            content=content,
            notice_type="General",
            priority="Normal",
            audience="All",
            created_by_id=reporter_id,
        )
        db.session.add(notice)
        db.session.commit()

        return {
            "notice_id": notice.id,
            "item_name": item_name,
            "item_type": item_type,
            "location": location,
            "status": "LOGGED_AND_BROADCAST",
        }
