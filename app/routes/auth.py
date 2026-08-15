from app.utils import utcnow
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify,
)
from werkzeug.exceptions import HTTPException
from app.models import db, User, Society, RegistrationRequest, AuditLog
from app.services.auth_service import AuthService
from app.services.registration_service import RegistrationService

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        mobile = AuthService.normalize_mobile(request.form.get("mobile", ""))
        password = request.form.get("password", "").strip()

        user = User.query.filter_by(mobile=mobile).first()
        if user:
            # Check rate limiting / failed attempts
            if user.failed_login_attempts >= 5:
                flash(
                    "Too many failed login attempts. Account temporarily locked.",
                    "danger",
                )
                return redirect(url_for("auth.login"))

            if user.check_password(password):
                # Reset failed attempts
                user.failed_login_attempts = 0

                # Account status handling
                if user.account_status == "ACTIVE":
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
                        return redirect(
                            url_for("auth.registration_status", registration_id=reg.id)
                        )
                    else:
                        flash("Your registration is pending approval.", "info")
                        return redirect(url_for("auth.login"))
                else:
                    # REJECTED, SUSPENDED, INACTIVE
                    db.session.commit()
                    flash(
                        "Your account is not active. Please contact support.", "danger"
                    )
                    return redirect(url_for("auth.login"))
            else:
                user.failed_login_attempts += 1
                db.session.commit()
                audit = AuditLog(
                    society_id=user.society_id,
                    user_id=user.id,
                    action="LOGIN_FAILURE",
                    details="Incorrect password",
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
        society_id = int(request.form.get("society_id"))
        building_id = int(request.form.get("building_id"))
        block_id = (
            int(request.form.get("block_id")) if request.form.get("block_id") else None
        )
        flat_id = int(request.form.get("flat_id"))
        occupancy_type = request.form.get("occupancy_type", "OWNER")
        password = request.form.get("password", "").strip()

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
            return redirect(url_for("auth.registration_status", registration_id=req.id))
        except HTTPException:
            raise
        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            flash(f"Registration failed: {str(e)}", "danger")

    societies = Society.query.all()
    return render_template("auth/register.html", societies=societies)


@auth_bp.route("/registration-status/<int:registration_id>")
def registration_status(registration_id):
    reg = RegistrationRequest.query.get_or_404(registration_id)
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

    code = AuthService.generate_otp(mobile)
    return jsonify(
        {"success": True, "message": f"OTP sent to {mobile}", "dev_otp": code}
    )


@auth_bp.route("/verify-otp", methods=["POST"])
def verify_otp():
    mobile = AuthService.normalize_mobile(request.form.get("mobile"))
    code = request.form.get("otp_code")

    valid, msg = AuthService.verify_otp(mobile, code)
    if valid:
        user = User.query.filter_by(mobile=mobile).first()
        token = AuthService.create_session(user, ip_address=request.remote_addr)
        session["user_id"] = user.id
        session["society_id"] = user.society_id
        session["role"] = user.role
        session["session_token"] = token
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

