"""Global Resident Event Photo Gallery APIs."""
from pathlib import Path
from flask import Blueprint, abort, current_app, jsonify, render_template, request, send_file, session
from sqlalchemy import func, or_, and_
from sqlalchemy.orm import joinedload
from app.models import Event, EventPhoto, Role, User, db
from app.services.event_photo_service import EventPhotoError, EventPhotoService
from app.utils import utcnow

event_photos_bp = Blueprint("event_photos", __name__)


@event_photos_bp.route("/resident/events")
def resident_events():
    user = _user()
    now = utcnow()
    event_filter = request.args.get("filter", "upcoming").lower()
    if event_filter not in {"upcoming", "ongoing", "past"}:
        event_filter = "upcoming"
    search = request.args.get("q", "").strip()

    # Events are tenant-scoped even though the UI presents a gallery.
    base_query = Event.query.filter(
        Event.society_id == user.society_id,
        Event.status.in_(("UPCOMING", "ACTIVE", "COMPLETED")),
    )

    all_society_events = base_query.order_by(
        Event.start_date.desc().nullslast(), Event.id.desc()
    ).all()

    # Dynamic counts for badges & tabs
    total_count = len(all_society_events)
    upcoming_count = 0
    ongoing_count = 0
    past_count = 0

    for ev in all_society_events:
        if ev.start_date and ev.start_date > now:
            upcoming_count += 1
        elif ev.start_date and ev.start_date <= now and (
            (ev.end_date and ev.end_date >= now)
            or (not ev.end_date and ev.start_date.date() == now.date())
        ):
            ongoing_count += 1
        else:
            past_count += 1

    # Filtered query for the active view
    query = base_query
    if search:
        query = query.filter(
            or_(
                Event.title.ilike(f"%{search}%"),
                Event.description.ilike(f"%{search}%"),
                Event.location.ilike(f"%{search}%"),
            )
        )

    # Robust date filtering handling NULL end_date
    if event_filter == "upcoming":
        query = query.filter(Event.start_date > now)
        events = query.order_by(Event.start_date.asc().nullslast(), Event.id.asc()).all()
    elif event_filter == "ongoing":
        query = query.filter(
            Event.start_date <= now,
            or_(
                Event.end_date >= now,
                and_(Event.end_date.is_(None), func.date(Event.start_date) == func.date(now)),
            ),
        )
        events = query.order_by(Event.start_date.desc().nullslast(), Event.id.desc()).all()
    else:  # past
        query = query.filter(
            or_(
                Event.end_date < now,
                and_(Event.end_date.is_(None), Event.start_date < now),
            )
        )
        events = query.order_by(Event.start_date.desc().nullslast(), Event.id.desc()).all()

    return render_template(
        "resident/events.html",
        events=events,
        all_society_events=all_society_events,
        selected_event_id=request.args.get("event", type=int),
        event_filter=event_filter,
        event_search=search,
        now=now,
        total_count=total_count,
        upcoming_count=upcoming_count,
        ongoing_count=ongoing_count,
        past_count=past_count,
    )


@event_photos_bp.route("/resident/events/<int:event_id>")
def event_detail(event_id):
    user = _user()
    # Event IDs are untrusted and must remain tenant-scoped.
    event = Event.query.filter(
        Event.id == event_id,
        Event.society_id == user.society_id,
        Event.status.in_(("UPCOMING", "ACTIVE", "COMPLETED")),
    ).first_or_404()

    page = max(request.args.get("page", 1, type=int), 1)
    media_filter = request.args.get("media", "ALL").upper()
    sort = request.args.get("sort", "NEWEST").upper()

    query = EventPhoto.query.filter_by(event_id=event.id, society_id=user.society_id, status="APPROVED")
    if media_filter in {"PHOTO", "VIDEO"}:
        query = query.filter_by(media_type=media_filter)
    if media_filter == "FEATURED":
        query = query.filter_by(is_featured=True)

    order = (
        (EventPhoto.created_at.asc(), EventPhoto.id.asc())
        if sort == "OLDEST"
        else (EventPhoto.is_featured.desc(), EventPhoto.created_at.desc(), EventPhoto.id.desc())
        if sort == "FEATURED"
        else (EventPhoto.created_at.desc(), EventPhoto.id.desc())
    )
    pagination = query.order_by(*order).paginate(page=page, per_page=24, error_out=False)

    approved_photo_count = EventPhoto.query.filter_by(
        event_id=event.id, society_id=user.society_id, status="APPROVED", media_type="PHOTO"
    ).count()
    approved_video_count = EventPhoto.query.filter_by(
        event_id=event.id, society_id=user.society_id, status="APPROVED", media_type="VIDEO"
    ).count()

    event_uploads = (
        EventPhoto.query.filter_by(event_id=event.id, society_id=user.society_id, uploaded_by_user_id=user.id)
        .order_by(EventPhoto.created_at.desc(), EventPhoto.id.desc())
        .all()
    )
    uploaded_count = len(event_uploads)
    uploads_open = event.status in {"UPCOMING", "ACTIVE", "COMPLETED"}

    return render_template(
        "resident/event_detail.html",
        event=event,
        pagination=pagination,
        event_uploads=event_uploads,
        approved_photo_count=approved_photo_count,
        approved_video_count=approved_video_count,
        uploads_open=uploads_open,
        uploaded_count=uploaded_count,
        media_filter=media_filter,
        gallery_sort=sort,
        now=utcnow(),
    )


@event_photos_bp.route("/resident/my-event-photos")
def resident_my_photos_page():
    user = _user()
    status = request.args.get("status", "").strip().upper()
    query = EventPhoto.query.filter_by(uploaded_by_user_id=user.id, society_id=user.society_id)
    if status in {"PENDING", "APPROVED", "REJECTED"}:
        query = query.filter_by(status=status)
    pagination = (
        query.options(joinedload(EventPhoto.event))
        .order_by(EventPhoto.created_at.desc(), EventPhoto.id.desc())
        .paginate(page=max(request.args.get("page", 1, type=int), 1), per_page=20, error_out=False)
    )
    return render_template(
        "resident/my_event_photos.html", pagination=pagination, selected_status=status
    )


def _user():
    user = db.session.get(User, session.get("user_id"))
    if (
        not user
        or user.account_status != "ACTIVE"
        or user.role != Role.RESIDENT
        or user.society_id is None
    ):
        abort(401)
    return user


def _json(photo, include_moderation=False):
    data = {
        "id": photo.id,
        "event_id": photo.event_id,
        "caption": photo.caption,
        "status": photo.status,
        "media_type": photo.media_type
        or ("VIDEO" if (photo.content_type or "").startswith("video/") else "PHOTO"),
        "content_type": photo.content_type,
        "original_filename": photo.original_filename,
        "file_size": photo.file_size,
        "width": photo.width,
        "height": photo.height,
        "created_at": photo.created_at.isoformat() if photo.created_at else None,
    }
    if include_moderation:
        data.update(
            {
                "uploaded_by_user_id": photo.uploaded_by_user_id,
                "original_filename": photo.original_filename,
                "rejection_reason": photo.rejection_reason,
            }
        )
    return data


def _error(exc):
    status = (
        404
        if exc.args and exc.args[0] in ("EVENT_NOT_FOUND", "PHOTO_NOT_FOUND")
        else 403
        if exc.args and exc.args[0] in ("UNAUTHORIZED", "FORBIDDEN")
        else 400
    )
    return jsonify({"error": str(exc)}), status


@event_photos_bp.route("/resident/events/<int:event_id>/photos", methods=["POST"])
def upload_photo(event_id):
    user = _user()
    try:
        files = request.files.getlist("photo")
        replacement_for_id = request.form.get("replacement_for_id", type=int)
        if not files or len(files) > current_app.config["EVENT_PHOTO_MAX_PER_UPLOAD"]:
            raise EventPhotoError("UPLOAD_BATCH_LIMIT_EXCEEDED")
        if replacement_for_id and len(files) != 1:
            raise EventPhotoError("INVALID_REPLACEMENT")
        photos = [
            EventPhotoService.upload(
                event_id, user, file, request.form.get("caption"), replacement_for_id
            )
            for file in files
        ]
        return jsonify({"items": [_json(photo) for photo in photos]}), 201
    except EventPhotoError as exc:
        return _error(exc)


@event_photos_bp.route("/resident/events/<int:event_id>/photos", methods=["GET"])
def gallery(event_id):
    user = _user()
    # Resident gallery is restricted to the authenticated tenant.
    event = Event.query.filter(
        Event.id == event_id,
        Event.status.in_(("UPCOMING", "ACTIVE", "COMPLETED")),
    ).first_or_404()
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 24, type=int), 1), 24)
    media_filter = request.args.get("media", "ALL").upper()
    query = EventPhoto.query.filter_by(event_id=event.id, society_id=user.society_id, status="APPROVED")
    if media_filter in {"PHOTO", "VIDEO"}:
        query = query.filter_by(media_type=media_filter)
    if media_filter == "FEATURED":
        query = query.filter_by(is_featured=True)
    sort = request.args.get("sort", "NEWEST").upper()
    order = (
        (EventPhoto.created_at.asc(), EventPhoto.id.asc())
        if sort == "OLDEST"
        else (EventPhoto.is_featured.desc(), EventPhoto.created_at.desc(), EventPhoto.id.desc())
        if sort == "FEATURED"
        else (EventPhoto.created_at.desc(), EventPhoto.id.desc())
    )
    pagination = query.order_by(*order).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify(
        {
            "items": [_json(p) for p in pagination.items],
            "page": pagination.page,
            "pages": pagination.pages,
            "total": pagination.total,
        }
    )


@event_photos_bp.route("/resident/photos", methods=["GET"])
def my_photos():
    user = _user()
    page = max(request.args.get("page", 1, type=int), 1)
    status = request.args.get("status", "").strip().upper()
    query = EventPhoto.query.filter_by(uploaded_by_user_id=user.id, society_id=user.society_id)
    if status in {"PENDING", "APPROVED", "REJECTED"}:
        query = query.filter_by(status=status)
    pagination = query.order_by(EventPhoto.created_at.desc(), EventPhoto.id.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    return jsonify(
        {
            "items": [_json(p) for p in pagination.items],
            "page": pagination.page,
            "pages": pagination.pages,
            "total": pagination.total,
        }
    )


@event_photos_bp.route("/resident/photos/<int:photo_id>/report", methods=["POST"])
def report_photo(photo_id):
    user = _user()
    payload = request.get_json(silent=True) or request.form
    try:
        report = EventPhotoService.report(
            user, photo_id, payload.get("reason"), payload.get("description")
        )
        return jsonify({"id": report.id, "status": report.status}), 201
    except EventPhotoError as exc:
        return _error(exc)


@event_photos_bp.route("/event-photos/<int:photo_id>/media", methods=["GET"])
def media(photo_id):
    user = _user()
    photo = EventPhoto.query.filter_by(id=photo_id, society_id=user.society_id).first_or_404()
    if photo.event.status not in ("UPCOMING", "ACTIVE", "COMPLETED"):
        abort(404)
    # Global visibility: Approved media is visible to all authenticated residents
    if (
        photo.status != "APPROVED"
        and photo.uploaded_by_user_id != user.id
        and user.role not in (Role.SUPER_ADMIN, Role.SOCIETY_ADMIN)
    ):
        abort(404)
    if (
        request.args.get("download") == "1"
        and user.role == Role.RESIDENT
        and not photo.event.allow_resident_downloads
    ):
        abort(403)
    path = Path(photo.file_path).resolve()
    root = Path(current_app.config["EVENT_PHOTO_STORAGE_DIR"]).resolve()
    if root not in path.parents or not path.is_file():
        abort(404)
    return send_file(
        str(path),
        mimetype=photo.content_type or "application/octet-stream",
        as_attachment=request.args.get("download") == "1",
        download_name=photo.original_filename or photo.filename,
    )
