"""Tenant-safe, transactional Event Photo Gallery workflows."""
import hashlib
import io
import os
import secrets
from pathlib import Path

from flask import current_app, session
from PIL import Image, UnidentifiedImageError
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

from app.models import (AuditLog, Event, EventPhoto, EventPhotoModerationHistory,
                        EventPhotoReport, EventPhotoStorageUsage, Role, db)
from app.utils import utcnow
from app.services.notification_service import NotificationService


class EventPhotoError(ValueError):
    pass


class EventPhotoService:
    REPORT_REASONS = {"INAPPROPRIATE_CONTENT", "WRONG_EVENT", "PRIVACY_CONCERN", "DUPLICATE", "OFFENSIVE_CONTENT", "OTHER"}

    @staticmethod
    def _event(event_id, society_id=None, lock=False):
        # Resident Events are global. Keep the argument for existing callers,
        # but do not make event ownership depend on the uploader's society.
        query = Event.query.filter_by(id=event_id)
        event = query.with_for_update().first() if lock else query.first()
        if not event:
            raise EventPhotoError("EVENT_NOT_FOUND")
        return event

    @staticmethod
    def _assert_upload_open(event):
        if event.status not in {"UPCOMING", "ACTIVE", "COMPLETED"}:
            raise EventPhotoError("PHOTO_UPLOADS_CLOSED")

    @staticmethod
    def _validate_image(file):
        if not file or not file.filename:
            raise EventPhotoError("INVALID_IMAGE")
        original = secure_filename(file.filename)
        extension = Path(original).suffix.lower().lstrip(".")
        if not original or extension not in current_app.config["EVENT_PHOTO_ALLOWED_EXTENSIONS"]:
            raise EventPhotoError("INVALID_IMAGE")
        max_bytes = current_app.config["EVENT_PHOTO_MAX_SIZE_MB"] * 1024 * 1024
        try:
            file.stream.seek(0)
            source = file.stream.read(max_bytes + 1)
            if len(source) > max_bytes:
                raise EventPhotoError("FILE_TOO_LARGE")
            with Image.open(io.BytesIO(source)) as image:
                image.verify()
            with Image.open(io.BytesIO(source)) as image:
                image.load()
                width, height = image.size
                if not width or not height or width > current_app.config["EVENT_PHOTO_MAX_WIDTH"] or height > current_app.config["EVENT_PHOTO_MAX_HEIGHT"]:
                    raise EventPhotoError("INVALID_IMAGE_DIMENSIONS")
                formats = {"JPEG": ("jpg", "image/jpeg"), "PNG": ("png", "image/png"), "WEBP": ("webp", "image/webp")}
                expected = {"JPEG": {"jpg", "jpeg"}, "PNG": {"png"}, "WEBP": {"webp"}}
                if image.format not in formats or extension not in expected[image.format]:
                    raise EventPhotoError("INVALID_IMAGE")
                output = io.BytesIO()
                # Re-encoding strips EXIF/GPS metadata before permanent storage.
                image.convert("RGB").save(output, format=image.format, **({"quality": 90, "optimize": True} if image.format == "JPEG" else {}))
                data = output.getvalue()
                if len(data) > max_bytes:
                    raise EventPhotoError("FILE_TOO_LARGE")
                stored_extension, content_type = formats[image.format]
                return original, stored_extension, content_type, width, height, data
        except EventPhotoError:
            raise
        except (UnidentifiedImageError, OSError, ValueError):
            raise EventPhotoError("INVALID_IMAGE")

    @staticmethod
    def _validate_video(file):
        if not file or not file.filename:
            raise EventPhotoError("INVALID_VIDEO")
        original = secure_filename(file.filename)
        extension = Path(original).suffix.lower().lstrip(".")
        config = current_app.config
        if not original or extension not in config["EVENT_VIDEO_ALLOWED_EXTENSIONS"]:
            raise EventPhotoError("INVALID_VIDEO")
        declared = (file.mimetype or "").lower()
        if declared not in config["EVENT_VIDEO_ALLOWED_MIME_TYPES"]:
            raise EventPhotoError("INVALID_VIDEO")
        max_bytes = config["EVENT_VIDEO_MAX_SIZE_MB"] * 1024 * 1024
        file.stream.seek(0)
        data = file.stream.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise EventPhotoError("FILE_TOO_LARGE")
        # Validate the container signature rather than trusting extension/MIME.
        signatures = {"mp4": (b"ftyp",), "mov": (b"ftyp",), "webm": (b"\x1a\x45\xdf\xa3",)}
        if not any(marker in data[:64] for marker in signatures.get(extension, ())):
            raise EventPhotoError("INVALID_VIDEO")
        return original, extension, declared, None, None, data
    @staticmethod
    def _usage(society_id):
        usage = EventPhotoStorageUsage.query.filter_by(society_id=society_id).with_for_update().first()
        if usage is None:
            usage = EventPhotoStorageUsage(society_id=society_id, used_bytes=0)
            db.session.add(usage)
            db.session.flush()
        return usage

    @staticmethod
    def _history(photo, actor_id, action, previous=None, new=None, reason=None):
        db.session.add(EventPhotoModerationHistory(society_id=photo.society_id, event_id=photo.event_id, photo_id=photo.id, actor_user_id=actor_id, action=action, previous_status=previous, new_status=new, reason=reason))

    @classmethod
    def upload(cls, event_id, user, file, caption=None, replacement_for_id=None):
        if not user or user.role != Role.RESIDENT or user.account_status != "ACTIVE":
            raise EventPhotoError("UNAUTHORIZED")
        is_video = (Path(file.filename).suffix.lower().lstrip(".") in current_app.config["EVENT_VIDEO_ALLOWED_EXTENSIONS"] or (file.mimetype or "").lower().startswith("video/"))
        original, extension, content_type, width, height, data = cls._validate_video(file) if is_video else cls._validate_image(file)
        media_type = "VIDEO" if is_video else "PHOTO"
        digest, size, temp_path, final_path, photo, committed = hashlib.sha256(data).hexdigest(), len(data), None, None, None, False
        try:
            event = cls._event(event_id, lock=True)
            cls._assert_upload_open(event)
            prior = None
            if replacement_for_id:
                prior = EventPhoto.query.filter_by(id=replacement_for_id, event_id=event.id, uploaded_by_user_id=user.id).with_for_update().first()
                if not prior or prior.status != "REJECTED":
                    raise EventPhotoError("INVALID_REPLACEMENT")
            if EventPhoto.query.filter_by(event_id=event.id, uploaded_by_user_id=user.id, content_hash=digest).first():
                raise EventPhotoError("DUPLICATE_MEDIA")
            if EventPhoto.query.filter_by(event_id=event.id, uploaded_by_user_id=user.id).count() >= current_app.config["EVENT_PHOTO_MAX_PER_USER_EVENT"]:
                raise EventPhotoError("UPLOAD_LIMIT_EXCEEDED")
            max_event = current_app.config["EVENT_PHOTO_MAX_EVENT_TOTAL"]
            if max_event and EventPhoto.query.filter_by(event_id=event.id, society_id=user.society_id).count() >= max_event:
                raise EventPhotoError("EVENT_PHOTO_LIMIT_EXCEEDED")
            usage = cls._usage(event.society_id)
            quota = current_app.config["EVENT_PHOTO_STORAGE_QUOTA_MB"] * 1024 * 1024
            if quota and usage.used_bytes + size > quota:
                raise EventPhotoError("STORAGE_QUOTA_EXCEEDED")
            filename = f"{secrets.token_hex(20)}.{extension}"
            directory = Path(current_app.config["EVENT_PHOTO_STORAGE_DIR"]).resolve() / str(event.society_id) / str(event.id)
            directory.mkdir(parents=True, exist_ok=True)
            final_path = (directory / filename).resolve()
            if Path(current_app.config["EVENT_PHOTO_STORAGE_DIR"]).resolve() not in final_path.parents:
                raise EventPhotoError("STORAGE_FAILED")
            temp_path = final_path.with_suffix(final_path.suffix + ".uploading")
            with open(temp_path, "xb") as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temp_path, final_path)
            photo = EventPhoto(society_id=event.society_id, event_id=event.id, uploaded_by_user_id=user.id, file_path=str(final_path), filename=filename, original_filename=original, caption=(caption or "").strip()[:255] or None, file_size=size, content_type=content_type, media_type=media_type, content_hash=digest, width=width, height=height, status="PENDING", replacement_for_id=prior.id if prior else None)
            db.session.add(photo)
            db.session.flush()
            usage.used_bytes = max(0, usage.used_bytes + size)
            cls._history(photo, user.id, "REUPLOAD" if prior else "UPLOAD", None, "PENDING")
            db.session.add(AuditLog(society_id=event.society_id, user_id=user.id, action="PHOTO_REUPLOADED" if prior else "PHOTO_UPLOADED", details=f"Event photo #{photo.id} for event #{event.id}"))
            db.session.commit()
            committed = True
            try:
                NotificationService.send_notification(recipient=user.mobile or user.email or "N/A", user_id=user.id, society_id=event.society_id, channel="In-App", subject="Event media submitted", message=f"Your {media_type.lower()} for {event.title} was submitted for approval.", category="General")
            except Exception:
                current_app.logger.warning("Unable to send event media submission notification", exc_info=True)
            return photo
        except EventPhotoError:
            db.session.rollback()
            raise
        except IntegrityError:
            db.session.rollback()
            raise EventPhotoError("DUPLICATE_MEDIA")
        except Exception:
            db.session.rollback()
            raise EventPhotoError("UPLOAD_FAILED")
        finally:
            if temp_path:
                temp_path.unlink(missing_ok=True)
            if final_path and not committed:
                final_path.unlink(missing_ok=True)

    @classmethod
    def report(cls, user, photo_id, reason, description=None):
        if not user or user.role != Role.RESIDENT or user.account_status != "ACTIVE":
            raise EventPhotoError("UNAUTHORIZED")
        reason = (reason or "").strip().upper()
        if reason not in cls.REPORT_REASONS:
            raise EventPhotoError("INVALID_REPORT_REASON")
        try:
            photo = EventPhoto.query.filter_by(id=photo_id, society_id=user.society_id, status="APPROVED").with_for_update().first()
            if not photo or not photo.event or photo.event.society_id != user.society_id:
                raise EventPhotoError("PHOTO_NOT_FOUND")
            if EventPhotoReport.query.filter_by(photo_id=photo.id, reported_by_user_id=user.id, reason=reason, status="PENDING").first():
                raise EventPhotoError("DUPLICATE_REPORT")
            report = EventPhotoReport(society_id=photo.society_id, event_id=photo.event_id, photo_id=photo.id, reported_by_user_id=user.id, reason=reason, description=(description or "").strip()[:1000] or None)
            db.session.add(report)
            cls._history(photo, user.id, "REPORT", photo.status, photo.status, reason)
            db.session.add(AuditLog(society_id=photo.society_id, user_id=user.id, action="PHOTO_REPORTED", details=f"Event photo #{photo.id}; reason={reason}"))
            db.session.commit()
            return report
        except IntegrityError:
            db.session.rollback()
            raise EventPhotoError("DUPLICATE_REPORT")
        except EventPhotoError:
            db.session.rollback()
            raise
        except Exception:
            db.session.rollback()
            raise EventPhotoError("REPORT_FAILED")


class EventPhotoModerationService:
    @staticmethod
    def _check_admin(admin, photo_id):
        if not admin or admin.role not in (Role.SUPER_ADMIN, Role.SOCIETY_ADMIN) or admin.account_status != "ACTIVE":
            raise EventPhotoError("FORBIDDEN")
        query = EventPhoto.query.filter_by(id=photo_id)
        if admin.role != Role.SUPER_ADMIN:
            society_id = session.get("society_id") or admin.society_id
            if society_id is not None:
                query = query.filter_by(society_id=society_id)
        photo = query.with_for_update().first()
        if not photo:
            raise EventPhotoError("PHOTO_NOT_FOUND")
        return photo

    @classmethod
    def _transition(cls, admin, photo_id, status, reason=None):
        try:
            photo = cls._check_admin(admin, photo_id)
            if photo.status == status:
                db.session.rollback()
                return EventPhoto.query.filter_by(id=photo_id).first()
            if photo.status != "PENDING":
                raise EventPhotoError("CURRENT_STATUS_" + photo.status)
            previous, now = photo.status, utcnow()
            photo.status = status
            if status == "APPROVED":
                photo.approved_by_user_id, photo.approved_at = admin.id, now
            else:
                photo.rejected_by_user_id, photo.rejected_at, photo.rejection_reason, photo.is_featured = admin.id, now, reason, False
                photo.featured_by_user_id, photo.featured_at = None, None
                if photo.event.cover_media_id == photo.id or photo.event.cover_photo_url == photo.file_path:
                    photo.event.cover_media_id, photo.event.cover_photo_url = None, None
            EventPhotoService._history(photo, admin.id, status, previous, status, reason)
            db.session.add(AuditLog(society_id=photo.society_id, user_id=admin.id, action="PHOTO_" + status, details=f"Event photo #{photo.id}"))
            db.session.commit()
            try:
                NotificationService.send_notification(recipient=photo.uploader.mobile or photo.uploader.email or "N/A", user_id=photo.uploaded_by_user_id, society_id=photo.society_id, channel="In-App", subject=f"Event media {status.lower()}", message=f"Your {photo.media_type.lower()} for {photo.event.title} was {status.lower()} and is now {'visible in the Event Gallery.' if status == 'APPROVED' else 'not visible in the Event Gallery.'}{(' Reason: ' + photo.rejection_reason) if photo.rejection_reason else ''}", category="General")
            except Exception:
                current_app.logger.warning("Unable to send event media moderation notification", exc_info=True)
            return photo
        except EventPhotoError:
            db.session.rollback()
            raise
        except Exception:
            db.session.rollback()
            raise EventPhotoError("MODERATION_FAILED")

    @classmethod
    def approve(cls, admin, photo_id): return cls._transition(admin, photo_id, "APPROVED")

    @classmethod
    def set_featured(cls, admin, photo_id, featured=True):
        try:
            photo = cls._check_admin(admin, photo_id)
            if featured and photo.status != "APPROVED":
                raise EventPhotoError("ONLY_APPROVED_MEDIA_CAN_BE_FEATURED")
            if photo.is_featured == featured:
                db.session.rollback()
                return photo
            now = utcnow()
            photo.is_featured = featured
            photo.featured_by_user_id = admin.id if featured else None
            photo.featured_at = now if featured else None
            EventPhotoService._history(photo, admin.id, "FEATURE" if featured else "UNFEATURE", photo.status, photo.status)
            db.session.add(AuditLog(society_id=photo.society_id, user_id=admin.id, action="PHOTO_FEATURED" if featured else "PHOTO_UNFEATURED", details=f"Event media #{photo.id}"))
            db.session.commit()
            return photo
        except EventPhotoError:
            db.session.rollback()
            raise
        except Exception:
            db.session.rollback()
            raise EventPhotoError("FEATURE_UPDATE_FAILED")

    @classmethod
    def set_cover(cls, admin, photo_id):
        try:
            photo = cls._check_admin(admin, photo_id)
            if photo.status != "APPROVED":
                raise EventPhotoError("ONLY_APPROVED_MEDIA_CAN_BE_COVER")
            event = Event.query.filter_by(id=photo.event_id).with_for_update().first()
            event.cover_media_id = photo.id
            event.cover_photo_url = photo.file_path
            db.session.add(AuditLog(society_id=photo.society_id, user_id=admin.id, action="EVENT_COVER_SET", details=f"Event #{event.id}; media #{photo.id}"))
            EventPhotoService._history(photo, admin.id, "SET_COVER", photo.status, photo.status)
            db.session.commit()
            return photo
        except EventPhotoError:
            db.session.rollback()
            raise
        except Exception:
            db.session.rollback()
            raise EventPhotoError("COVER_UPDATE_FAILED")

    @classmethod
    def clear_cover(cls, admin, photo_id):
        try:
            photo = cls._check_admin(admin, photo_id)
            event = Event.query.filter_by(id=photo.event_id).with_for_update().first()
            if event and (event.cover_media_id == photo.id or event.cover_photo_url == photo.file_path):
                event.cover_media_id, event.cover_photo_url = None, None
                db.session.add(AuditLog(society_id=photo.society_id, user_id=admin.id, action="EVENT_COVER_CLEARED", details=f"Event #{event.id}"))
                EventPhotoService._history(photo, admin.id, "CLEAR_COVER", photo.status, photo.status)
                db.session.commit()
            else:
                db.session.rollback()
            return photo
        except EventPhotoError:
            db.session.rollback()
            raise
        except Exception:
            db.session.rollback()
            raise EventPhotoError("COVER_UPDATE_FAILED")

    @classmethod
    def bulk_transition(cls, admin, photo_ids, status, reason=None):
        if status not in {"APPROVED", "REJECTED"}:
            raise EventPhotoError("INVALID_MODERATION_STATUS")
        if status == "REJECTED" and not (reason or "").strip():
            raise EventPhotoError("REJECTION_REASON_REQUIRED")
        results = []
        for photo_id in dict.fromkeys(photo_ids or []):
            try:
                photo = cls._transition(admin, int(photo_id), status, reason)
                results.append({"id": int(photo_id), "status": photo.status, "success": True})
            except EventPhotoError as exc:
                results.append({"id": int(photo_id), "status": "UNKNOWN", "success": False, "error": str(exc)})
        return results
    @classmethod
    def reject(cls, admin, photo_id, reason):
        reason = (reason or "").strip()
        if not reason or len(reason) > 255:
            raise EventPhotoError("REJECTION_REASON_REQUIRED")
        return cls._transition(admin, photo_id, "REJECTED", reason)

    @classmethod
    def resolve_report(cls, admin, report_id, action, reason=None):
        action = (action or "").strip().upper()
        if action not in {"DISMISS", "ARCHIVE", "REMOVE"}:
            raise EventPhotoError("INVALID_REPORT_ACTION")
        try:
            if not admin or admin.role not in (Role.SUPER_ADMIN, Role.SOCIETY_ADMIN):
                raise EventPhotoError("FORBIDDEN")
            query = EventPhotoReport.query.filter_by(id=report_id)
            if admin.role != Role.SUPER_ADMIN:
                society_id = session.get("society_id") or admin.society_id
                if society_id is not None:
                    query = query.filter_by(society_id=society_id)
            report = query.with_for_update().first()
            if not report:
                raise EventPhotoError("REPORT_NOT_FOUND")
            if report.status != "PENDING":
                db.session.rollback()
                return EventPhotoReport.query.filter_by(id=report_id).first()
            photo, now = EventPhoto.query.filter_by(id=report.photo_id).with_for_update().first(), utcnow()
            report.reviewed_by_user_id, report.reviewed_at, report.admin_action = admin.id, now, action
            report.status = "DISMISSED" if action == "DISMISS" else "ACTION_TAKEN"
            removed_path = None
            if action in {"ARCHIVE", "REMOVE"} and photo and photo.status == "APPROVED":
                previous_status = photo.status
                new_status = "REMOVED" if action == "REMOVE" else "ARCHIVED"
                photo.status, photo.is_featured = new_status, False
                photo.archived_by_user_id, photo.archived_at, photo.archive_reason = admin.id, now, (reason or action)[:255]
                if photo.event.cover_photo_url == photo.file_path:
                    photo.event.cover_photo_url = None
                if action == "REMOVE":
                    if photo.event.cover_media_id == photo.id or photo.event.cover_photo_url == photo.file_path:
                        photo.event.cover_media_id, photo.event.cover_photo_url = None, None
                    usage = EventPhotoService._usage(photo.society_id)
                    usage.used_bytes = max(0, usage.used_bytes - (photo.file_size or 0))
                    removed_path = photo.file_path
                EventPhotoService._history(photo, admin.id, action, previous_status, new_status, reason)
            db.session.add(AuditLog(society_id=report.society_id, user_id=admin.id, action="PHOTO_REPORT_" + action, details=f"Report #{report.id}"))
            db.session.commit()
            if removed_path:
                try:
                    Path(removed_path).resolve().unlink(missing_ok=True)
                except OSError:
                    current_app.logger.warning("Unable to remove event photo storage object after removal")
            return report
        except EventPhotoError:
            db.session.rollback()
            raise
        except Exception:
            db.session.rollback()
            raise EventPhotoError("REPORT_RESOLUTION_FAILED")
