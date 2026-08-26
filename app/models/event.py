from app.models.tenant import db
from app.utils import utcnow


class Event(db.Model):
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    cover_photo_url = db.Column(db.String(255), nullable=True)
    cover_media_id = db.Column(
        db.Integer,
        db.ForeignKey("event_photos.id"),
        nullable=True,
        index=True,
    )
    allow_resident_downloads = db.Column(
        db.Boolean, default=False, nullable=False
    )
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    photo_upload_deadline = db.Column(db.DateTime, nullable=True)
    location = db.Column(
        db.String(150),
        default="Society Clubhouse / Grounds",
        nullable=True,
    )
    status = db.Column(
        db.String(30),
        default="ACTIVE",
        nullable=False,
        index=True,
    )  # UPCOMING, ACTIVE, COMPLETED, ARCHIVED
    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
    )
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=utcnow,
        onupdate=utcnow,
    )

    photos = db.relationship(
        "EventPhoto",
        backref="event",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="EventPhoto.created_at.desc()",
        foreign_keys="[EventPhoto.event_id]",
    )
    cover_media = db.relationship(
        "EventPhoto",
        foreign_keys=[cover_media_id],
        lazy=True,
    )
    creator = db.relationship(
        "User",
        foreign_keys=[created_by_id],
        lazy=True,
    )
    society = db.relationship(
        "Society",
        backref="events",
        lazy=True,
    )

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def approved_photos_count(self):
        return sum(1 for p in self.photos if p.status == "APPROVED")

    @property
    def pending_photos_count(self):
        return sum(1 for p in self.photos if p.status == "PENDING")

    @property
    def total_photos_count(self):
        return len(self.photos)


class EventPhoto(db.Model):
    __tablename__ = "event_photos"

    __table_args__ = (
        db.Index(
            "ix_event_photos_event_status",
            "event_id",
            "status",
        ),
        db.Index(
            "ix_event_photos_society_status",
            "society_id",
            "status",
        ),
        db.Index(
            "ix_event_photos_uploader_status",
            "uploaded_by_user_id",
            "status",
        ),
        db.Index(
            "ix_event_photos_event_hash",
            "event_id",
            "content_hash",
        ),
        db.UniqueConstraint(
            "event_id",
            "uploaded_by_user_id",
            "content_hash",
            name="uq_event_photo_uploader_hash",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    society_id = db.Column(
        db.Integer,
        db.ForeignKey("societies.id"),
        nullable=False,
        index=True,
    )

    event_id = db.Column(
        db.Integer,
        db.ForeignKey("events.id"),
        nullable=False,
        index=True,
    )

    uploaded_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    file_path = db.Column(
        db.String(255),
        nullable=False,
    )

    filename = db.Column(
        db.String(255),
        nullable=False,
    )

    original_filename = db.Column(
        db.String(255),
        nullable=True,
    )

    caption = db.Column(
        db.String(255),
        nullable=True,
    )

    file_size = db.Column(
        db.Integer,
        nullable=True,
    )

    content_type = db.Column(
        db.String(50),
        default="image/jpeg",
        nullable=True,
    )

    media_type = db.Column(
        db.String(10),
        default="PHOTO",
        nullable=False,
        index=True,
    )

    content_hash = db.Column(
        db.String(64),
        nullable=True,
        index=True,
    )

    width = db.Column(
        db.Integer,
        nullable=True,
    )

    height = db.Column(
        db.Integer,
        nullable=True,
    )

    status = db.Column(
        db.String(20),
        default="PENDING",
        nullable=False,
        index=True,
    )  # PENDING, APPROVED, REJECTED, ARCHIVED

    is_featured = db.Column(
        db.Boolean,
        default=False,
        nullable=False,
    )

    approved_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
    )

    approved_at = db.Column(
        db.DateTime,
        nullable=True,
    )

    rejected_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
    )

    rejected_at = db.Column(
        db.DateTime,
        nullable=True,
    )

    rejection_reason = db.Column(
        db.String(255),
        nullable=True,
    )

    replacement_for_id = db.Column(
        db.Integer,
        db.ForeignKey("event_photos.id"),
        nullable=True,
        index=True,
    )

    archived_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
    )

    featured_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
    )

    featured_at = db.Column(
        db.DateTime,
        nullable=True,
    )

    archived_at = db.Column(
        db.DateTime,
        nullable=True,
    )

    archive_reason = db.Column(
        db.String(255),
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime,
        default=utcnow,
        index=True,
    )

    updated_at = db.Column(
        db.DateTime,
        default=utcnow,
        onupdate=utcnow,
    )

    uploader = db.relationship(
        "User",
        foreign_keys=[uploaded_by_user_id],
        backref="uploaded_event_photos",
        lazy=True,
    )

    approver = db.relationship(
        "User",
        foreign_keys=[approved_by_user_id],
        lazy=True,
    )

    rejecter = db.relationship(
        "User",
        foreign_keys=[rejected_by_user_id],
        lazy=True,
    )

    society = db.relationship(
        "Society",
        backref="event_photos",
        lazy=True,
    )

    replacement_for = db.relationship(
        "EventPhoto",
        remote_side=[id],
        backref="replacements",
        lazy=True,
    )

    reports = db.relationship(
        "EventPhotoReport",
        backref="photo",
        lazy=True,
        cascade="all, delete-orphan",
    )

    history = db.relationship(
        "EventPhotoModerationHistory",
        backref="photo",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def is_video(self):
        return self.media_type == "VIDEO"


class EventPhotoStorageUsage(db.Model):
    __tablename__ = "event_photo_storage_usage"

    society_id = db.Column(
        db.Integer,
        db.ForeignKey("societies.id"),
        primary_key=True,
    )

    used_bytes = db.Column(
        db.BigInteger,
        nullable=False,
        default=0,
    )

    updated_at = db.Column(
        db.DateTime,
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )


class EventPhotoModerationHistory(db.Model):
    __tablename__ = "event_photo_moderation_history"

    __table_args__ = (
        db.Index(
            "ix_event_photo_history_photo_created",
            "photo_id",
            "created_at",
        ),
    )

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    society_id = db.Column(
        db.Integer,
        db.ForeignKey("societies.id"),
        nullable=False,
        index=True,
    )

    event_id = db.Column(
        db.Integer,
        db.ForeignKey("events.id"),
        nullable=False,
        index=True,
    )

    photo_id = db.Column(
        db.Integer,
        db.ForeignKey("event_photos.id"),
        nullable=False,
        index=True,
    )

    actor_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
    )

    action = db.Column(
        db.String(20),
        nullable=False,
    )

    previous_status = db.Column(
        db.String(20),
        nullable=True,
    )

    new_status = db.Column(
        db.String(20),
        nullable=True,
    )

    reason = db.Column(
        db.String(255),
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime,
        default=utcnow,
        nullable=False,
    )


class EventPhotoReport(db.Model):
    __tablename__ = "event_photo_reports"

    __table_args__ = (
        db.Index(
            "ix_event_photo_reports_society_status",
            "society_id",
            "status",
        ),
        db.UniqueConstraint(
            "photo_id",
            "reported_by_user_id",
            "reason",
            "status",
            name="uq_event_photo_active_report",
        ),
    )

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    society_id = db.Column(
        db.Integer,
        db.ForeignKey("societies.id"),
        nullable=False,
        index=True,
    )

    event_id = db.Column(
        db.Integer,
        db.ForeignKey("events.id"),
        nullable=False,
        index=True,
    )

    photo_id = db.Column(
        db.Integer,
        db.ForeignKey("event_photos.id"),
        nullable=False,
        index=True,
    )

    reported_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    reason = db.Column(
        db.String(40),
        nullable=False,
    )

    description = db.Column(
        db.String(1000),
        nullable=True,
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="PENDING",
        index=True,
    )

    reviewed_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
    )

    reviewed_at = db.Column(
        db.DateTime,
        nullable=True,
    )

    admin_action = db.Column(
        db.String(20),
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime,
        default=utcnow,
        nullable=False,
    )

    updated_at = db.Column(
        db.DateTime,
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )