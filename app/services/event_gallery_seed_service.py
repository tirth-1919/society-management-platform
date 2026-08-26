"""Idempotent system content and initial seed data for the resident event gallery."""
from datetime import datetime
from pathlib import Path
from flask import current_app
from app.models import db, Event, EventPhoto
from app.utils import utcnow


STARTER_EVENTS_CONFIG = [
    {
        "title": "Navratri 2024",
        "description": "Join the community for nine nights of Garba, music, food, and celebration.",
        "location": "Society Community Ground",
        "start_date": datetime(2024, 10, 3, 18, 0),
        "end_date": datetime(2024, 10, 12, 23, 0),
        "status": "COMPLETED",
        "primary_color": "#f97316",
        "secondary_color": "#d946ef",
        "icon_label": "Garba & Dandiya Nights 2024",
        "gallery_count": 5,
        "gallery_captions": [
            "Garba Night 1 Celebration",
            "Dandiya Raas with Residents",
            "Traditional Costume Competition",
            "Community Feast & Food Stalls",
            "Grand Finale & Prize Distribution",
        ],
    },
    {
        "title": "Diwali 2024",
        "description": "Celebrate the festival of lights with decorations, cultural programs, and community dinner.",
        "location": "Community Hall / Society Ground",
        "start_date": datetime(2024, 10, 31, 18, 30),
        "end_date": datetime(2024, 11, 3, 22, 30),
        "status": "COMPLETED",
        "primary_color": "#eab308",
        "secondary_color": "#b45309",
        "icon_label": "Festival of Lights 2024",
        "gallery_count": 5,
        "gallery_captions": [
            "Grand Diya Lighting & Rangoli Display",
            "Children's Cultural Program",
            "Musical Night & Community Dinner",
            "Society Lantern & Light Decorations",
            "Diwali Mela & Community Games",
        ],
    },
    {
        "title": "Navratri 2025",
        "description": "Join the Sunrise Heights community for nine nights of Garba, music, food, and celebration.",
        "location": "Society Ground",
        "start_date": datetime(2025, 9, 22, 18, 0),
        "end_date": datetime(2025, 10, 1, 23, 0),
        "status": "COMPLETED",
        "primary_color": "#d946ef",
        "secondary_color": "#f97316",
        "icon_label": "Garba & Dandiya Nights",
        "gallery_count": 5,
        "gallery_captions": [
            "Opening Aarti & Garba Night 1",
            "Dandiya Raas with Society Residents",
            "Traditional Costume Competition",
            "Community Feast & Food Stalls",
            "Mega Finale & Award Distribution",
        ],
    },
    {
        "title": "Diwali 2025",
        "description": "Celebrate Diwali together with the Sunrise Heights community with lights, decorations, cultural activities, and celebrations.",
        "location": "Community Hall / Society Ground",
        "start_date": datetime(2025, 10, 20, 18, 30),
        "end_date": datetime(2025, 10, 23, 22, 30),
        "status": "COMPLETED",
        "primary_color": "#f59e0b",
        "secondary_color": "#b45309",
        "icon_label": "Festival of Lights",
        "gallery_count": 5,
        "gallery_captions": [
            "Grand Diya Lighting & Rangoli Display",
            "Children's Cultural Program",
            "Musical Night & Community Dinner",
            "Society Decoration & Lantern Lighting",
            "Diwali Mela & Games",
        ],
    },
    {
        "title": "Holi 2026",
        "description": "Celebrate the festival of colors with music, organic colors, sweets, and joy at Sunrise Heights.",
        "location": "Clubhouse Lawn",
        "start_date": datetime(2026, 3, 4, 9, 30),
        "end_date": datetime(2026, 3, 4, 14, 0),
        "status": "COMPLETED",
        "primary_color": "#ec4899",
        "secondary_color": "#06b6d4",
        "icon_label": "Festival of Colors",
        "gallery_count": 2,
        "gallery_captions": [
            "Organic Gulal Celebration",
            "Music & Dhol Gathering at Clubhouse Lawn",
        ],
    },
    {
        "title": "Annual Sports Day 2026",
        "description": "Annual sports competitions for all age groups including cricket, badminton, athletics, and fun games.",
        "location": "Society Sports Arena",
        "start_date": datetime(2026, 11, 15, 8, 0),
        "end_date": datetime(2026, 11, 15, 18, 0),
        "status": "UPCOMING",
        "primary_color": "#10b981",
        "secondary_color": "#0284c7",
        "icon_label": "Sports & Fitness Meet",
        "gallery_count": 1,
        "gallery_captions": [
            "Sports Arena Setup & Schedule Announcement",
        ],
    },
    {
        "title": "Republic Day 2026",
        "description": "Flag hoisting ceremony, cultural performances by society children, and community breakfast.",
        "location": "Main Gate Plaza",
        "start_date": datetime(2026, 1, 26, 8, 30),
        "end_date": datetime(2026, 1, 26, 12, 0),
        "status": "COMPLETED",
        "primary_color": "#ff9933",
        "secondary_color": "#138808",
        "icon_label": "77th Republic Day Ceremony",
        "gallery_count": 1,
        "gallery_captions": [
            "Flag Hoisting & Patriotic Performances",
        ],
    },
    {
        "title": "Independence Day 2026",
        "description": "Independence Day flag hoisting, patriotic songs, awards for meritorious students, and high tea.",
        "location": "Main Gate Plaza",
        "start_date": datetime(2026, 8, 15, 8, 30),
        "end_date": datetime(2026, 8, 15, 12, 30),
        "status": "COMPLETED",
        "primary_color": "#ff9933",
        "secondary_color": "#000080",
        "icon_label": "Independence Day Celebrations",
        "gallery_count": 1,
        "gallery_captions": [
            "Tricolor Hoisting & Student Awards",
        ],
    },
]


def _build_svg(title, subtitle, primary_color, secondary_color, index=None):
    """Generate a rich, styled SVG banner for event cover / gallery cards."""
    badge = f"Photo #{index}" if index else "Official Event Cover"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 800" width="1200" height="800">
  <defs>
    <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{primary_color}" stop-opacity="1" />
      <stop offset="100%" stop-color="{secondary_color}" stop-opacity="1" />
    </linearGradient>
    <pattern id="pattern-circles" x="0" y="0" width="60" height="60" patternUnits="userSpaceOnUse">
      <circle cx="30" cy="30" r="4" fill="#ffffff" fill-opacity="0.12" />
    </pattern>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="8" stdDeviation="16" flood-color="#000000" flood-opacity="0.35" />
    </filter>
  </defs>

  <!-- Background Base with Gradient -->
  <rect width="1200" height="800" fill="url(#grad)" />
  <rect width="1200" height="800" fill="url(#pattern-circles)" />

  <!-- Decorative Accents -->
  <circle cx="1100" cy="120" r="180" fill="#ffffff" fill-opacity="0.08" />
  <circle cx="100" cy="700" r="220" fill="#000000" fill-opacity="0.12" />

  <!-- Card Overlay -->
  <rect x="120" y="160" width="960" height="480" rx="24" fill="#0f172a" fill-opacity="0.75" filter="url(#shadow)" stroke="#ffffff" stroke-opacity="0.2" stroke-width="2" />

  <!-- Badge -->
  <rect x="170" y="210" width="220" height="44" rx="22" fill="{primary_color}" fill-opacity="0.9" />
  <text x="280" y="238" fill="#ffffff" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="18" font-weight="700" text-anchor="middle" letter-spacing="1">{badge.upper()}</text>

  <!-- Community Tag -->
  <text x="1030" y="238" fill="#94a3b8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="16" font-weight="600" text-anchor="end">COMMUNITY EVENTS</text>

  <!-- Title & Subtitle -->
  <text x="170" y="340" fill="#ffffff" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="56" font-weight="800">{title}</text>
  <text x="170" y="410" fill="#e2e8f0" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="28" font-weight="500">{subtitle}</text>

  <!-- Bottom Divider & Details -->
  <line x1="170" y1="460" x2="1030" y2="460" stroke="#ffffff" stroke-opacity="0.2" stroke-width="1.5" />
  <text x="170" y="530" fill="#38bdf8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="22" font-weight="600">✦ Verified Community Event</text>
  <text x="1030" y="530" fill="#cbd5e1" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="20" text-anchor="end">Resident Portal</text>
</svg>"""


class EventGallerySeedService:
    @staticmethod
    def ensure_defaults(society_id, admin_user):
        """Idempotently seed community events and initial approved gallery media."""
        root = Path(current_app.config["EVENT_PHOTO_STORAGE_DIR"]).resolve()
        created_photos = []

        for cfg in STARTER_EVENTS_CONFIG:
            title = cfg["title"]
            event = Event.query.filter_by(society_id=society_id, title=title).first()

            if not event:
                event = Event(
                    society_id=society_id,
                    title=title,
                    description=cfg["description"],
                    location=cfg["location"],
                    start_date=cfg["start_date"],
                    end_date=cfg["end_date"],
                    status=cfg["status"],
                    created_by_id=admin_user.id,
                )
                db.session.add(event)
                db.session.flush()
            else:
                # Update/repair missing details without overwriting custom edits
                event.description = event.description or cfg["description"]
                event.location = event.location or cfg["location"]
                event.start_date = event.start_date or cfg["start_date"]
                event.end_date = event.end_date or cfg["end_date"]
                if not event.status:
                    event.status = cfg["status"]

            # Directory for event media
            directory = root / str(society_id) / str(event.id)
            directory.mkdir(parents=True, exist_ok=True)

            first_photo = None
            gallery_count = cfg.get("gallery_count", 1)
            gallery_captions = cfg.get("gallery_captions", [])

            for index in range(1, gallery_count + 1):
                original_filename = f"default-{title.lower().replace(' ', '-')}-{index}.svg"
                caption = gallery_captions[index - 1] if index <= len(gallery_captions) else f"{title} Highlight {index}"
                path = directory / original_filename

                if not path.exists():
                    svg_content = _build_svg(
                        title=title,
                        subtitle=caption,
                        primary_color=cfg["primary_color"],
                        secondary_color=cfg["secondary_color"],
                        index=index,
                    )
                    path.write_text(svg_content, encoding="utf-8")

                photo = EventPhoto.query.filter_by(
                    event_id=event.id,
                    original_filename=original_filename,
                ).first()

                file_size = path.stat().st_size

                if photo:
                    # Ensure status is APPROVED for seeded admin media
                    photo.society_id = society_id
                    photo.status = "APPROVED"
                    photo.media_type = "PHOTO"
                    photo.file_path = str(path)
                    photo.filename = original_filename
                    photo.file_size = file_size
                    photo.content_type = "image/svg+xml"
                    photo.caption = photo.caption or caption
                    photo.approved_by_user_id = photo.approved_by_user_id or admin_user.id
                    photo.approved_at = photo.approved_at or utcnow()
                else:
                    photo = EventPhoto(
                        society_id=society_id,
                        event_id=event.id,
                        uploaded_by_user_id=admin_user.id,
                        file_path=str(path),
                        filename=original_filename,
                        original_filename=original_filename,
                        caption=caption,
                        file_size=file_size,
                        content_type="image/svg+xml",
                        media_type="PHOTO",
                        content_hash=f"default-{event.id}-{index}",
                        width=1200,
                        height=800,
                        status="APPROVED",
                        approved_by_user_id=admin_user.id,
                        approved_at=utcnow(),
                    )
                    db.session.add(photo)
                    db.session.flush()
                    created_photos.append(photo)

                if index == 1:
                    first_photo = photo

            # Link cover media if not already set
            if first_photo and not event.cover_media_id:
                event.cover_media_id = first_photo.id

        db.session.commit()
        return created_photos
