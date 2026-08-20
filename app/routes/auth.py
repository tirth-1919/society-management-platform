from app.utils import utcnow
from datetime import timedelta
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify,
    current_app,
    abort,
)
from werkzeug.exceptions import HTTPException
from app.models import db, User, Society, RegistrationRequest, AuditLog, Flat, Building, Block
from app.services.auth_service import AuthService
from app.services.registration_service import (
    RegistrationService,
    check_flat_availability,
    get_flat_property_key,
)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        mobile = AuthService.normalize_mobile(request.form.get("mobile", ""))
        password = request.form.get("password", "").strip()

        user = User.query.filter_by(mobile=mobile).first()
        if user:
            # Check account lockout
            if user.locked_until:
                if user.locked_until > utcnow():
                    mins_left = int((user.locked_until - utcnow()).total_seconds() / 60) + 1
                    flash(
                        f"Account temporarily locked due to multiple failed login attempts. Please try again in {mins_left} minute(s).",
                        "danger",
                    )
                    return redirect(url_for("auth.login"))
                else:
                    user.locked_until = None
                    user.failed_login_attempts = 0
                    db.session.commit()

            if user.check_password(password):
                # Reset failed attempts and lockout
                user.failed_login_attempts = 0
                user.locked_until = None

                # Account status handling
                if user.account_status == "ACTIVE":
                    # Regenerate/clear session to prevent session fixation
                    session.clear()
                    token = AuthService.create_session(
                        user,
                        device_info=request.headers.get("User-Agent", "Browser"),
                        ip_address=request.remote_addr,
                    )
                    session["user_id"] = user.id
                    session["society_id"] = user.society_id
                    session["role"] = user.role
                    session["session_token"] = token
                    user.last_login_at = utcnow()
                    db.session.commit()

                    flash(f"Welcome back, {user.full_name}!", "success")
                    return redirect(url_for("main.dashboard"))
                elif user.account_status == "PENDING_APPROVAL":
                    db.session.commit()
                    reg = (
                        RegistrationRequest.query.filter_by(user_id=user.id)
                        .order_by(RegistrationRequest.created_at.desc())
                        .first()
                    )
                    if reg:
                        session["registration_request_id"] = reg.id
                        return redirect(
                            url_for("auth.registration_status", registration_id=reg.id)
                        )
                    else:
                        flash("Your registration is pending approval.", "info")
                        return redirect(url_for("auth.login"))
                else:
                    # REJECTED, SUSPENDED, INACTIVE: show the applicant's own
                    # rejected registration status without creating a session.
                    db.session.commit()
                    reg = (
                        RegistrationRequest.query.filter_by(user_id=user.id)
                        .order_by(RegistrationRequest.created_at.desc())
                        .first()
                    )
                    if reg and reg.status == "REJECTED":
                        session["registration_request_id"] = reg.id
                        return redirect(url_for("auth.registration_status", registration_id=reg.id))
                    flash(
                        "Your account is not active. Please contact support.", "danger"
                    )
                    return redirect(url_for("auth.login"))
            else:
                user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
                if user.failed_login_attempts >= 5:
                    user.locked_until = utcnow() + timedelta(minutes=15)
                db.session.commit()
                audit = AuditLog(
                    society_id=user.society_id,
                    user_id=user.id,
                    action="LOGIN_FAILURE",
                    details=f"Incorrect password attempt {user.failed_login_attempts}",
                )
                db.session.add(audit)
                db.session.commit()

        flash("Invalid mobile number or password", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        mobile = AuthService.normalize_mobile(request.form.get("mobile", ""))
        email = request.form.get("email", "").strip() or None
        society_id_raw = (request.form.get("society_id") or "").strip()
        flat_id_raw = (request.form.get("flat_id") or "").strip()
        if not society_id_raw or not flat_id_raw:
            flash("Please select a society and flat number.", "danger")
            societies = Society.query.order_by(Society.name.asc()).all()
            return render_template("auth/register.html", societies=societies), 400
        try:
            society_id = int(society_id_raw)
            flat_id = int(flat_id_raw)
        except (TypeError, ValueError):
            flash("Invalid society or flat selection.", "danger")
            societies = Society.query.order_by(Society.name.asc()).all()
            return render_template("auth/register.html", societies=societies), 400
        selected_society = db.session.get(Society, society_id)
        if not selected_society:
            abort(403, description="Selected society does not exist")

        # Load by ID first so an existing flat from another society is treated
        # as a tampered hierarchy (403), while a genuinely missing flat keeps
        # the existing user-facing 400 response below.
        submitted_flat = db.session.get(Flat, flat_id)
        if submitted_flat is None:
            flat_obj = None
        elif submitted_flat.society_id != society_id:
            abort(403, description="Selected flat does not belong to the selected society")
        else:
            flat_obj = submitted_flat
        building_id_raw = request.form.get("building_id")
        block_id_raw = request.form.get("block_id")
        try:
            selected_building_id = int(building_id_raw) if building_id_raw else None
            selected_block_id = int(block_id_raw) if block_id_raw else None
        except (TypeError, ValueError):
            abort(400, description="Invalid block or wing selection")

        # Validate the complete hierarchy server-side; never trust IDs from the browser.
        selected_building = (
            Building.query.filter_by(id=selected_building_id, society_id=society_id).first()
            if selected_building_id else None
        )
        if selected_building_id and not selected_building:
            abort(403, description="Selected block does not belong to the selected society")
        if flat_obj and selected_building_id and flat_obj.building_id != selected_building_id:
            abort(403, description="Selected flat does not belong to the selected block or wing")
        if selected_block_id:
            selected_block = Block.query.filter_by(
                id=selected_block_id, society_id=society_id
            ).first()
            if not selected_block or (selected_building_id and selected_block.building_id != selected_building_id):
                abort(403, description="Selected block does not belong to the selected society or wing")
        if not flat_obj:
            flash("The selected flat does not belong to the selected society.", "danger")
            societies = Society.query.order_by(Society.name.asc()).all()
            return render_template("auth/register.html", societies=societies), 400

        building_id = selected_building_id or (flat_obj.building_id if flat_obj else None)
        block_id = flat_obj.block_id if (flat_obj and flat_obj.block_id) else selected_block_id
        occupancy_type = request.form.get("occupancy_type", "OWNER")
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        # Browser forms require confirmation; keep compatibility with trusted
        # legacy/API submissions that predate the confirmation field.
        if confirm_password and password != confirm_password:
            flash("Password and Confirm Password must match.", "danger")
            societies = Society.query.order_by(Society.name.asc()).all()
            return render_template("auth/register.html", societies=societies), 400
        # ── FLAT AVAILABILITY PRE-CHECK (server-side, user-friendly) ──
        try:
            is_available, occupant_name = check_flat_availability(society_id, flat_id)
            if not is_available:
                flat_obj = Flat.query.filter_by(id=flat_id, society_id=society_id).first()
                prop_key = get_flat_property_key(flat_obj) if flat_obj else f"Flat #{flat_id}"
                flash(
                    f"Flat {prop_key} is already registered or has a pending application. "
                    "Please contact the society administrator.",
                    "danger",
                )
                societies = Society.query.order_by(Society.name.asc()).all()
                return render_template("auth/register.html", societies=societies)
        except Exception:
            pass  # Let register_resident() handle validation errors

        try:
            req = RegistrationService.register_resident(
                full_name=full_name,
                mobile=mobile,
                email=email,
                society_id=society_id,
                building_id=building_id,
                block_id=block_id,
                flat_id=flat_id,
                occupancy_type=occupancy_type,
                password=password,
            )
            flash(
                "Registration request submitted successfully. Awaiting admin approval.",
                "info",
            )
            session["registration_request_id"] = req.id
            return redirect(url_for("auth.registration_status", registration_id=req.id))
        except HTTPException:
            raise
        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            flash(f"Registration failed: {str(e)}", "danger")

    societies = Society.query.order_by(Society.name.asc()).all()
    for soc in societies:
        try:
            from app.services.tenant_service import TenantService
            TenantService.ensure_default_blocks_and_flats(soc.id)
        except Exception:
            pass
    return render_template("auth/register.html", societies=societies)


@auth_bp.route("/registration-status/<int:registration_id>")
def registration_status(registration_id):
    reg = RegistrationRequest.query.get_or_404(registration_id)
    user_id = session.get("user_id")
    session_request_id = session.get("registration_request_id")
    owns_session_request = session_request_id == reg.id
    owns_authenticated_request = user_id is not None and reg.user_id == user_id
    if not (owns_session_request or owns_authenticated_request):
        abort(403, description="You are not authorized to view this registration request")
    return render_template("auth/registration_status.html", reg=reg, status=reg.status)


@auth_bp.route("/otp-login", methods=["POST"])
def send_otp():
    mobile = (
        request.json.get("mobile") if request.is_json else request.form.get("mobile")
    )
    mobile = AuthService.normalize_mobile(mobile)
    if not mobile:
        return jsonify({"success": False, "message": "Mobile number required"}), 400

    user = User.query.filter_by(mobile=mobile).first()
    if not user:
        return jsonify(
            {"success": False, "message": "Mobile number not registered"}
        ), 404

    try:
        code = AuthService.generate_otp(mobile)
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 429

    payload = {"success": True, "message": f"OTP sent to {mobile}"}
    if current_app.config.get("DEBUG") or current_app.config.get("TESTING"):
        payload["dev_otp"] = code

    return jsonify(payload)


@auth_bp.route("/verify-otp", methods=["POST"])
def verify_otp():
    mobile = AuthService.normalize_mobile(request.form.get("mobile"))
    code = request.form.get("otp_code")

    valid, msg = AuthService.verify_otp(mobile, code)
    if valid:
        user = User.query.filter_by(mobile=mobile).first()
        if not user:
            flash("User not found.", "danger")
            return redirect(url_for("auth.login"))

        if user.account_status != "ACTIVE":
            if user.account_status == "PENDING_APPROVAL":
                flash("Your registration is pending approval.", "info")
            else:
                flash("Your account is not active. Please contact support.", "danger")
            return redirect(url_for("auth.login"))

        session.clear()
        token = AuthService.create_session(
            user,
            device_info=request.headers.get("User-Agent", "Browser"),
            ip_address=request.remote_addr,
        )
        session["user_id"] = user.id
        session["society_id"] = user.society_id
        session["role"] = user.role
        session["session_token"] = token
        user.last_login_at = utcnow()
        db.session.commit()

        flash("OTP Verified Successfully!", "success")
        return redirect(url_for("main.dashboard"))

    flash(msg, "danger")
    return redirect(url_for("auth.login"))


@auth_bp.route("/logout")
def logout():
    token = session.get("session_token")
    if token:
        AuthService.invalidate_session(token)
    session.clear()
    flash("You have been logged out securely.", "info")
    return redirect(url_for("auth.login"))

