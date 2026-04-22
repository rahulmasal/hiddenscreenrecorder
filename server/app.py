"""
Screen Recorder Server
Main Flask application with modular architecture
"""

import os
import sys
import logging
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, render_template, redirect, url_for, flash, session, request
from flask_cors import CORS
from flask_migrate import Migrate

# Add shared module to path
# Check multiple locations for the shared module
_shared_paths = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "shared"),  # server/shared
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "shared"
    ),  # ../shared (project root)
]
for _shared_path in _shared_paths:
    if os.path.isdir(_shared_path):
        sys.path.insert(0, _shared_path)
        break

# Import local modules
from config import settings
from models import db, init_db, Client, License, Video, AuditLog
from auth import auth_manager, require_auth, require_csrf, rate_limit, create_session, destroy_session
from routes.api import api_bp, legacy_bp

# Import license manager
from license_manager import LicenseManager

# Configure logging with structured logging support
try:
    from logging_config import setup_logging, ContextLogger

    setup_logging(
        level=settings.log_level,
        log_format="colored",  # Use 'structured' for JSON logging in production
        service_name="screen-recorder-server",
    )
    logger = logging.getLogger(__name__)
except ImportError:
    # Fallback to basic logging if logging_config is not available
    logging.basicConfig(
        level=getattr(logging, settings.log_level), format=settings.log_format
    )
    logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = settings.secret_key
app.config["MAX_CONTENT_LENGTH"] = settings.max_content_length
app.config["SQLALCHEMY_DATABASE_URI"] = settings.database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Enable CORS with restricted origins
CORS(app, origins=settings.cors_origins, supports_credentials=True)

# Initialize database
init_db(app)

# Initialize Flask-Migrate
migrate = Migrate(app, db)

# Register blueprints
app.register_blueprint(api_bp)
app.register_blueprint(legacy_bp)

# Initialize WebSocket manager (optional)
try:
    from websocket_manager import ws_manager

    if ws_manager.init_app(app):
        logger.info("WebSocket manager initialized")
    else:
        logger.info("WebSocket manager not available (flask-socketio not installed)")
except ImportError:
    logger.info("WebSocket manager module not available")


# ============ Security Headers ============
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    # Note: In production with proper SSL, you might want to add:
    # response.headers['Content-Security-Policy'] = "default-src 'self'"
    return response


# ============ HTTPS Enforcement ============
if settings.enforce_https:
    from flask_talisman import Talisman

    talisman = Talisman(app, force_https=True)
    logger.info("HTTPS enforcement enabled")


# ============ Key Management ============


def init_keys():
    """Initialize RSA keys for license signing"""
    private_key_path = settings.keys_folder / "private_key.pem"
    public_key_path = settings.keys_folder / "public_key.pem"

    if private_key_path.exists() and public_key_path.exists():
        with open(private_key_path, "r") as f:
            private_key = f.read()
        with open(public_key_path, "r") as f:
            public_key = f.read()
        logger.info("Loaded existing keys")
    else:
        private_key, public_key = LicenseManager.generate_key_pair()
        with open(private_key_path, "w") as f:
            f.write(private_key)
        with open(public_key_path, "w") as f:
            f.write(public_key)
        logger.info("Generated new keys")

    return private_key, public_key


PRIVATE_KEY, PUBLIC_KEY = init_keys()

# Initialize license manager
license_manager = LicenseManager()
license_manager.load_private_key(PRIVATE_KEY)


# ============ Template Setup ============

# Ensure templates directory exists (templates are standalone .html files)
Path(__file__).parent.joinpath("templates").mkdir(parents=True, exist_ok=True)

# Add datetime filter for Jinja templates
app.jinja_env.filters["datetime"] = lambda x: (
    datetime.fromtimestamp(x).strftime("%Y-%m-%d %H:%M:%S") if x else "N/A"
)


# ============ Admin Routes ============


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """Admin login page"""
    error = None
    if request.method == "POST":
        password = request.form.get("password")
        csrf_token = request.form.get("csrf_token")

        # Validate CSRF
        if not auth_manager.validate_csrf_token(csrf_token):
            error = "Invalid CSRF token"
        else:
            is_valid, token = create_session(password)
            if is_valid:
                return redirect(url_for("admin_dashboard"))
            else:
                error = "Invalid password"

    return render_template(
        "login.html", error=error, csrf_token=auth_manager.generate_csrf_token()
    )


@app.route("/admin/logout", methods=["POST"])
@require_csrf
def admin_logout():
    """Admin logout (requires POST for CSRF protection)"""
    destroy_session()
    return redirect(url_for("admin_login"))


@app.route("/admin")
@require_auth
def admin_dashboard():
    """Admin dashboard"""
    from flask import request

    # Get statistics from database
    clients = (
        db.session.execute(db.select(Client).order_by(Client.last_seen.desc()))
        .scalars()
        .all()
    )

    # Get active licenses
    licenses = db.session.execute(
        db.select(License).where(License.expires_at > datetime.now(timezone.utc))
    ).scalars().all()

    # Get aggregated video statistics
    from sqlalchemy import func
    video_stats = db.session.execute(
        db.select(
            Video.client_id,
            func.count(Video.id).label('video_count'),
            func.sum(Video.file_size).label('total_size')
        ).group_by(Video.client_id)
    ).all()
    
    # Map stats by client_id
    stats_map = {stat.client_id: {'video_count': stat.video_count, 'total_size': stat.total_size or 0} for stat in video_stats}

    # Prepare client data
    client_data = []
    for client in clients:
        stats = stats_map.get(client.id, {'video_count': 0, 'total_size': 0})
        client_data.append(
            {
                "machine_id": client.machine_id,
                "video_count": stats['video_count'],
                "total_size": stats['total_size'],
                "last_seen": client.last_seen,
            }
        )

    # Calculate overall totals
    total_videos = sum(c["video_count"] for c in client_data)
    total_size = sum(c["total_size"] for c in client_data)

    return render_template(
        "dashboard.html",
        clients=client_data,
        licenses=[
            {
                "machine_id": l.machine_id,
                "expires_at": l.expires_at.isoformat() if l.expires_at else "",
            }
            for l in licenses
        ],
        total_videos=total_videos,
        total_size=total_size,
        total_clients=len(clients),
        csrf_token=auth_manager.generate_csrf_token(),
    )


@app.route("/admin/generate-license", methods=["GET", "POST"])
@require_auth
@require_csrf
def generate_license():
    """Generate a new license"""
    from flask import request
    from datetime import timedelta, timezone

    if request.method == "POST":
        machine_id = request.form.get("machine_id")
        expiry_days = int(request.form.get("expiry_days", 365))
        features = request.form.getlist("features")

        if not machine_id:
            flash("Machine ID is required", "error")
            return redirect(url_for("generate_license"))

        # Generate license
        features_dict = {
            "recording": "recording" in features,
            "upload": "upload" in features,
        }

        license_key = license_manager.generate_license(
            machine_id, expiry_days=expiry_days, features=features_dict
        )

        # Link license to client if client exists (#8 fix)
        now = datetime.now(timezone.utc)
        client = db.session.execute(
            db.select(Client).where(Client.machine_id == machine_id)
        ).scalar_one_or_none()

        license_obj = License(
            machine_id=machine_id,
            license_key=license_key,
            expires_at=now + timedelta(days=expiry_days),
            features=features_dict,
            client_id=client.id if client else None,
        )
        db.session.add(license_obj)
        db.session.commit()

        license_info = {
            "machine_id": machine_id,
            "license_key": license_key,
            "expires_at": (now + timedelta(days=expiry_days)).isoformat(),
            "features": features_dict,
        }

        flash("License generated successfully", "success")
        return render_template("license_result.html", license_info=license_info)

    return render_template(
        "generate_license.html", csrf_token=auth_manager.generate_csrf_token()
    )


@app.route("/admin/clients/<machine_id>")
@require_auth
def view_client(machine_id):
    """View client details and videos"""
    client = db.session.execute(
        db.select(Client).where(Client.machine_id == machine_id)
    ).scalar_one_or_none()

    if not client:
        flash("Client not found", "error")
        return redirect(url_for("admin_dashboard"))

    videos = (
        db.session.execute(
            db.select(Video)
            .where(Video.client_id == client.id)
            .order_by(Video.upload_time.desc())
        )
        .scalars()
        .all()
    )

    video_data = [
        {"filename": v.filename, "size": v.file_size, "created": v.upload_time}
        for v in videos
    ]

    return render_template(
        "client.html",
        machine_id=machine_id,
        videos=video_data,
        csrf_token=auth_manager.generate_csrf_token(),
    )


@app.route("/admin/download/<machine_id>/<filename>")
@require_auth
def download_video(machine_id, filename):
    """Download a video file"""
    from flask import send_file

    filepath = settings.upload_folder / machine_id / filename

    if not filepath.exists():
        flash("File not found", "error")
        return redirect(url_for("view_client", machine_id=machine_id))

    return send_file(filepath, as_attachment=True)


@app.route("/admin/delete-license/<machine_id>", methods=["POST"])
@require_auth
@require_csrf
def delete_license(machine_id):
    """Delete a license"""
    license_obj = db.session.execute(
        db.select(License).where(License.machine_id == machine_id)
    ).scalar_one_or_none()

    if license_obj:
        db.session.delete(license_obj)
        db.session.commit()
        flash("License deleted", "success")
    else:
        flash("License not found", "error")

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/delete-video/<machine_id>/<filename>", methods=["POST"])
@require_auth
@require_csrf
def delete_video(machine_id, filename):
    """Delete a video file"""
    filepath = settings.upload_folder / machine_id / filename

    if filepath.exists():
        filepath.unlink()
        # Also delete from database — filter by client to avoid deleting another client's video (#12 fix)
        client = db.session.execute(
            db.select(Client).where(Client.machine_id == machine_id)
        ).scalar_one_or_none()
        if client:
            video = db.session.execute(
                db.select(Video).where(
                    Video.filename == filename,
                    Video.client_id == client.id,
                )
            ).scalar_one_or_none()
            if video:
                db.session.delete(video)
                db.session.commit()
        flash("Video deleted", "success")
    else:
        flash("File not found", "error")

    return redirect(url_for("view_client", machine_id=machine_id))


@app.route("/admin/logs")
@require_auth
def admin_logs():
    """Connection and activity logs page"""
    from datetime import timedelta

    # Query params
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 50))
    filter_action = request.args.get("action", "").strip()
    filter_machine_id = request.args.get("machine_id", "").strip()

    per_page = max(10, min(per_page, 200))  # clamp
    offset = (page - 1) * per_page

    now = datetime.now(timezone.utc)
    since_24h = now - timedelta(hours=24)

    # ---- Summary counters ----
    active_clients = (
        db.session.execute(
            db.select(db.func.count(Client.id)).where(Client.is_active == True)
        ).scalar()
        or 0
    )

    uploads_24h = (
        db.session.execute(
            db.select(db.func.count(AuditLog.id)).where(
                AuditLog.action == "video_upload",
                AuditLog.timestamp >= since_24h,
            )
        ).scalar()
        or 0
    )

    heartbeats_24h = (
        db.session.execute(
            db.select(db.func.count(AuditLog.id)).where(
                AuditLog.action == "heartbeat",
                AuditLog.timestamp >= since_24h,
            )
        ).scalar()
        or 0
    )

    errors_24h = (
        db.session.execute(
            db.select(db.func.count(AuditLog.id)).where(
                AuditLog.action.like("%error%"),
                AuditLog.timestamp >= since_24h,
            )
        ).scalar()
        or 0
    )

    # ---- Client online status (last heartbeat within 2 minutes = online) ----
    clients_raw = (
        db.session.execute(db.select(Client).order_by(Client.last_seen.desc()))
        .scalars()
        .all()
    )
    clients_status = [
        {
            "machine_id": c.machine_id,
            "online": c.last_seen is not None
            and (now - c.last_seen).total_seconds() < 120,
            "first_seen": (
                c.first_seen.strftime("%Y-%m-%d %H:%M:%S") if c.first_seen else "N/A"
            ),
            "last_seen": (
                c.last_seen.strftime("%Y-%m-%d %H:%M:%S") if c.last_seen else "N/A"
            ),
        }
        for c in clients_raw
    ]

    # ---- Build log query with optional filters ----
    log_query = db.select(AuditLog).order_by(AuditLog.timestamp.desc())
    count_query = db.select(db.func.count(AuditLog.id))

    if filter_action:
        log_query = log_query.where(AuditLog.action == filter_action)
        count_query = count_query.where(AuditLog.action == filter_action)

    # Get total count via SQL (never loads all rows into memory)
    total_logs = db.session.execute(count_query).scalar() or 0
    total_pages = max(1, (total_logs + per_page - 1) // per_page)

    # Apply SQL-level pagination
    log_query = log_query.limit(per_page).offset(offset)
    logs_raw = db.session.execute(log_query).scalars().all()

    # Resolve machine_id for each log via details or entity_id
    log_data = []
    for log in logs_raw:
        machine_id_label = None
        # Check details dict first (heartbeat stores machine_id there)
        if log.details and "machine_id" in log.details:
            mid = log.details["machine_id"]
            if mid:
                machine_id_label = (mid[:16] + "...") if len(mid) > 16 else mid
        elif log.action == "video_upload" and log.entity_id:
            video = db.session.get(Video, log.entity_id)
            if video and video.client and video.client.machine_id:
                machine_id_label = video.client.machine_id[:16] + "..."

        # If a machine_id text filter is active, skip non-matching rows
        if filter_machine_id:
            if not machine_id_label or filter_machine_id.lower() not in machine_id_label.lower():
                continue

        log_data.append(
            {
                "timestamp": (
                    log.timestamp.strftime("%Y-%m-%d %H:%M:%S") if log.timestamp else ""
                ),
                "action": log.action,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "machine_id": machine_id_label,
                "ip_address": log.ip_address,
                "details": log.details or {},
            }
        )

    return render_template(
        "connection_logs.html",
        logs=log_data,
        total_logs=total_logs,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        filter_action=filter_action,
        filter_machine_id=filter_machine_id,
        active_clients=active_clients,
        uploads_24h=uploads_24h,
        heartbeats_24h=heartbeats_24h,
        errors_24h=errors_24h,
        clients=clients_status,
    )


# ============ Main ============

if __name__ == "__main__":
    port = settings.port
    debug = settings.debug

    logger.info(f"Starting server on port {port}")
    app.run(host=settings.host, port=port, debug=debug)
