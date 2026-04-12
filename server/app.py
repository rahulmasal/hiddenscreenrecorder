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

# Enable CORS
CORS(app)

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


# ============ Template Creation ============


def create_templates():
    """Create HTML templates"""
    templates_dir = Path(__file__).parent / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)

    # Templates are created only if they don't exist
    templates = {
        "login.html": """<!DOCTYPE html>
<html>
<head>
    <title>Admin Login - Screen Recorder Server</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <div class="container mt-5">
        <div class="row justify-content-center">
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">
                        <h4 class="mb-0">Admin Login</h4>
                    </div>
                    <div class="card-body">
                        {% if error %}
                        <div class="alert alert-danger">{{ error }}</div>
                        {% endif %}
                        <form method="POST">
                            <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                            <div class="mb-3">
                                <label class="form-label">Password</label>
                                <input type="password" name="password" class="form-control" required>
                            </div>
                            <button type="submit" class="btn btn-primary w-100">Login</button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>""",
        "connection_logs.html": """<!DOCTYPE html>
<html>
<head>
    <title>Connection Logs - Screen Recorder Server</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .badge-upload    { background-color:#198754; }
        .badge-heartbeat { background-color:#0dcaf0; color:#000; }
        .badge-validate  { background-color:#ffc107; color:#000; }
        .badge-error     { background-color:#dc3545; }
        .badge-other     { background-color:#6c757d; }
        .log-row:hover   { background-color:#f8f9fa; }
        .filter-bar      { background:#f1f3f5; border-radius:8px; padding:14px 18px; margin-bottom:18px; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/admin">Screen Recorder Admin</a>
            <div>
                <a href="/admin/logs" class="btn btn-outline-info btn-sm me-2">Logs</a>
                <a href="/admin/generate-license" class="btn btn-success btn-sm me-2">Generate License</a>
                <a href="/admin/logout" class="btn btn-outline-light btn-sm">Logout</a>
            </div>
        </div>
    </nav>
    <div class="container mt-4">
        <div class="d-flex justify-content-between align-items-center mb-3">
            <h4 class="mb-0">Connection &amp; Activity Logs</h4>
            <span class="text-muted small">Showing {{ logs|length }} of {{ total_logs }} entries</span>
        </div>

        <!-- Summary cards -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="card text-white bg-primary">
                    <div class="card-body py-2">
                        <h6 class="mb-0">Active Clients</h6>
                        <h3 class="mb-0">{{ active_clients }}</h3>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-white bg-success">
                    <div class="card-body py-2">
                        <h6 class="mb-0">Video Uploads (24h)</h6>
                        <h3 class="mb-0">{{ uploads_24h }}</h3>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-white bg-info" style="color:#000">
                    <div class="card-body py-2">
                        <h6 class="mb-0">Heartbeats (24h)</h6>
                        <h3 class="mb-0">{{ heartbeats_24h }}</h3>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-white bg-danger">
                    <div class="card-body py-2">
                        <h6 class="mb-0">Errors (24h)</h6>
                        <h3 class="mb-0">{{ errors_24h }}</h3>
                    </div>
                </div>
            </div>
        </div>

        <!-- Client online status -->
        {% if clients %}
        <div class="card mb-4">
            <div class="card-header"><h6 class="mb-0">Client Online Status</h6></div>
            <div class="card-body p-0">
                <table class="table table-sm mb-0">
                    <thead class="table-light">
                        <tr>
                            <th>Machine ID</th>
                            <th>Status</th>
                            <th>First Seen</th>
                            <th>Last Seen</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for c in clients %}
                        <tr>
                            <td><code><a href="/admin/clients/{{ c.machine_id }}">{{ c.machine_id[:16] }}...</a></code></td>
                            <td>
                                {% if c.online %}
                                <span class="badge bg-success">Online</span>
                                {% else %}
                                <span class="badge bg-secondary">Offline</span>
                                {% endif %}
                            </td>
                            <td>{{ c.first_seen }}</td>
                            <td>{{ c.last_seen }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        {% endif %}

        <!-- Filter bar -->
        <form method="GET" action="/admin/logs" class="filter-bar row g-2 align-items-end">
            <div class="col-md-3">
                <label class="form-label mb-1 small fw-bold">Event Type</label>
                <select name="action" class="form-select form-select-sm">
                    <option value="">All events</option>
                    <option value="video_upload"  {% if filter_action=='video_upload'  %}selected{% endif %}>Video Upload</option>
                    <option value="heartbeat"     {% if filter_action=='heartbeat'     %}selected{% endif %}>Heartbeat</option>
                    <option value="license_valid" {% if filter_action=='license_valid' %}selected{% endif %}>License Valid</option>
                    <option value="license_invalid" {% if filter_action=='license_invalid' %}selected{% endif %}>License Invalid</option>
                </select>
            </div>
            <div class="col-md-3">
                <label class="form-label mb-1 small fw-bold">Machine ID (contains)</label>
                <input type="text" name="machine_id" class="form-control form-control-sm"
                       value="{{ filter_machine_id }}" placeholder="e.g. abc123">
            </div>
            <div class="col-md-2">
                <label class="form-label mb-1 small fw-bold">Per page</label>
                <select name="per_page" class="form-select form-select-sm">
                    {% for n in [25, 50, 100, 200] %}
                    <option value="{{ n }}" {% if per_page==n %}selected{% endif %}>{{ n }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="col-md-2">
                <button type="submit" class="btn btn-primary btn-sm w-100">Filter</button>
            </div>
            <div class="col-md-2">
                <a href="/admin/logs" class="btn btn-outline-secondary btn-sm w-100">Reset</a>
            </div>
        </form>

        <!-- Log table -->
        <div class="card">
            <div class="card-body p-0">
                <table class="table table-sm table-bordered mb-0">
                    <thead class="table-dark">
                        <tr>
                            <th style="width:160px">Timestamp</th>
                            <th style="width:140px">Event</th>
                            <th>Machine / Entity</th>
                            <th>IP Address</th>
                            <th>Details</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for log in logs %}
                        <tr class="log-row">
                            <td class="text-nowrap small">{{ log.timestamp }}</td>
                            <td>
                                {% if log.action == 'video_upload' %}
                                    <span class="badge badge-upload">Upload</span>
                                {% elif log.action == 'heartbeat' %}
                                    <span class="badge badge-heartbeat">Heartbeat</span>
                                {% elif 'license' in log.action %}
                                    <span class="badge badge-validate">{{ log.action }}</span>
                                {% elif 'error' in log.action %}
                                    <span class="badge badge-error">Error</span>
                                {% else %}
                                    <span class="badge badge-other">{{ log.action }}</span>
                                {% endif %}
                            </td>
                            <td class="small"><code>{{ log.machine_id or (log.entity_type + ' #' + (log.entity_id|string)) }}</code></td>
                            <td class="small">{{ log.ip_address or '-' }}</td>
                            <td class="small">
                                {% if log.details %}
                                    {% for k, v in log.details.items() %}
                                        <span class="text-muted">{{ k }}:</span> {{ v }}&nbsp;
                                    {% endfor %}
                                {% else %}-{% endif %}
                            </td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="5" class="text-center text-muted py-4">No log entries found</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Pagination -->
        {% if total_pages > 1 %}
        <nav class="mt-3">
            <ul class="pagination pagination-sm justify-content-center">
                {% for p in range(1, total_pages + 1) %}
                <li class="page-item {% if p == page %}active{% endif %}">
                    <a class="page-link"
                       href="/admin/logs?page={{ p }}&per_page={{ per_page }}&action={{ filter_action }}&machine_id={{ filter_machine_id }}"
                    >{{ p }}</a>
                </li>
                {% endfor %}
            </ul>
        </nav>
        {% endif %}
    </div>
    <script>
        // Auto-refresh every 30 seconds
        setTimeout(() => location.reload(), 30000);
    </script>
</body>
</html>""",
        "dashboard.html": """<!DOCTYPE html>
<html>
<head>
    <title>Dashboard - Screen Recorder Server</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/admin">Screen Recorder Admin</a>
            <div>
                <a href="/admin/logs" class="btn btn-outline-info btn-sm me-2">Logs</a>
                <a href="/admin/generate-license" class="btn btn-success btn-sm me-2">Generate License</a>
                <a href="/admin/logout" class="btn btn-outline-light btn-sm">Logout</a>
            </div>
        </div>
    </nav>
    <div class="container mt-4">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="card text-white bg-primary">
                    <div class="card-body">
                        <h6>Total Clients</h6>
                        <h2>{{ total_clients }}</h2>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-white bg-success">
                    <div class="card-body">
                        <h6>Total Videos</h6>
                        <h2>{{ total_videos }}</h2>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-white bg-info">
                    <div class="card-body">
                        <h6>Total Storage</h6>
                        <h2>{{ "%.2f"|format(total_size / 1024 / 1024 / 1024) }} GB</h2>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-white bg-secondary">
                    <div class="card-body">
                        <h6>Active Licenses</h6>
                        <h2>{{ licenses|length }}</h2>
                    </div>
                </div>
            </div>
        </div>
        <div class="row">
            <div class="col-md-8">
                <div class="card">
                    <div class="card-header"><h5>Clients</h5></div>
                    <div class="card-body">
                        {% if clients %}
                        <table class="table">
                            <thead><tr><th>Machine ID</th><th>Videos</th><th>Storage</th><th>Actions</th></tr></thead>
                            <tbody>
                                {% for client in clients %}
                                <tr>
                                    <td><code>{{ client.machine_id[:12] }}...</code></td>
                                    <td>{{ client.video_count }}</td>
                                    <td>{{ "%.2f"|format(client.total_size / 1024 / 1024) }} MB</td>
                                    <td><a href="/admin/clients/{{ client.machine_id }}" class="btn btn-sm btn-primary">View</a></td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                        {% else %}
                        <p class="text-muted">No clients yet</p>
                        {% endif %}
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header"><h5>Licenses</h5></div>
                    <div class="card-body">
                        {% if licenses %}
                        <table class="table table-sm">
                            <thead><tr><th>Machine ID</th><th>Expires</th><th>Actions</th></tr></thead>
                            <tbody>
                                {% for license in licenses %}
                                <tr>
                                    <td><code>{{ license.machine_id[:8] }}...</code></td>
                                    <td>{{ license.expires_at[:10] }}</td>
                                    <td>
                                        <form action="/admin/delete-license/{{ license.machine_id }}" method="POST" style="display:inline">
                                            <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                                            <button type="submit" class="btn btn-sm btn-danger" onclick="return confirm('Delete this license?')">Delete</button>
                                        </form>
                                    </td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                        {% else %}
                        <p class="text-muted">No licenses yet</p>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>""",
        "generate_license.html": """<!DOCTYPE html>
<html>
<head>
    <title>Generate License - Screen Recorder Server</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/admin">Screen Recorder Admin</a>
            <div>
                <a href="/admin/logs" class="btn btn-outline-info btn-sm me-2">Logs</a>
                <a href="/admin/logout" class="btn btn-outline-light btn-sm">Logout</a>
            </div>
        </div>
    </nav>
    <div class="container mt-4">
        <div class="row justify-content-center">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header"><h5>Generate New License</h5></div>
                    <div class="card-body">
                        <form method="POST">
                            <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                            <div class="mb-3">
                                <label class="form-label">Machine ID</label>
                                <input type="text" name="machine_id" class="form-control" required placeholder="Enter client machine ID">
                                <small class="text-muted">Run the client with --get-id to get the machine ID</small>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Expiry (Days)</label>
                                <input type="number" name="expiry_days" class="form-control" value="365" min="1">
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Features</label>
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" name="features" value="recording" checked>
                                    <label class="form-check-label">Recording</label>
                                </div>
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" name="features" value="upload" checked>
                                    <label class="form-check-label">Upload</label>
                                </div>
                            </div>
                            <button type="submit" class="btn btn-primary w-100">Generate License</button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>""",
        "license_result.html": """<!DOCTYPE html>
<html>
<head>
    <title>License Generated - Screen Recorder Server</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/admin">Screen Recorder Admin</a>
            <div>
                <a href="/admin/logs" class="btn btn-outline-info btn-sm me-2">Logs</a>
                <a href="/admin/logout" class="btn btn-outline-light btn-sm">Logout</a>
            </div>
        </div>
    </nav>
    <div class="container mt-4">
        <div class="row justify-content-center">
            <div class="col-md-8">
                <div class="card">
                    <div class="card-header bg-success text-white"><h5>License Generated Successfully</h5></div>
                    <div class="card-body">
                        <p><strong>Machine ID:</strong> <code>{{ license_info.machine_id }}</code></p>
                        <p><strong>Expires:</strong> {{ license_info.expires_at }}</p>
                        <p><strong>Features:</strong> {{ license_info.features }}</p>
                        <hr>
                        <label class="form-label"><strong>License Key (save as license.key):</strong></label>
                        <textarea class="form-control" rows="5" readonly>{{ license_info.license_key }}</textarea>
                        <div class="mt-3">
                            <button onclick="copyToClipboard()" class="btn btn-primary">Copy to Clipboard</button>
                            <a href="/admin" class="btn btn-secondary">Back to Dashboard</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <script>
    function copyToClipboard() {
        const textarea = document.querySelector('textarea');
        const text = textarea.value;
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(function() {
                alert('License key copied to clipboard!');
            }).catch(function() {
                textarea.select();
                document.execCommand('copy');
                alert('License key copied to clipboard!');
            });
        } else {
            textarea.select();
            document.execCommand('copy');
            alert('License key copied to clipboard!');
        }
    }
    </script>
</body>
</html>""",
        "client.html": """<!DOCTYPE html>
<html>
<head>
    <title>Client {{ machine_id }} - Screen Recorder Server</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/admin">Screen Recorder Admin</a>
            <div>
                <a href="/admin/logs" class="btn btn-outline-info btn-sm me-2">Logs</a>
                <a href="/admin/logout" class="btn btn-outline-light btn-sm">Logout</a>
            </div>
        </div>
    </nav>
    <div class="container mt-4">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h2>Client: <code>{{ machine_id }}</code></h2>
            <a href="/admin" class="btn btn-secondary">Back to Dashboard</a>
        </div>
        {% if videos %}
        <table class="table">
            <thead><tr><th>Filename</th><th>Size</th><th>Created</th><th>Actions</th></tr></thead>
            <tbody>
                {% for video in videos %}
                <tr>
                    <td>{{ video.filename }}</td>
                    <td>{{ "%.2f"|format(video.size / 1024 / 1024) }} MB</td>
                    <td>{{ video.created }}</td>
                    <td>
                        <a href="/admin/download/{{ machine_id }}/{{ video.filename }}" class="btn btn-sm btn-success">Download</a>
                        <form action="/admin/delete-video/{{ machine_id }}/{{ video.filename }}" method="POST" style="display:inline">
                            <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                            <button type="submit" class="btn btn-sm btn-danger" onclick="return confirm('Delete this video?')">Delete</button>
                        </form>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <div class="alert alert-info">No videos uploaded yet</div>
        {% endif %}
    </div>
</body>
</html>""",
    }

    for name, content in templates.items():
        template_path = templates_dir / name
        # Always overwrite so code changes to templates take effect (#15 fix)
        with open(template_path, "w") as f:
            f.write(content)

    # Add datetime filter
    app.jinja_env.filters["datetime"] = lambda x: (
        datetime.fromtimestamp(x).strftime("%Y-%m-%d %H:%M:%S") if x else "N/A"
    )


create_templates()


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


@app.route("/admin/logout")
def admin_logout():
    """Admin logout"""
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

    licenses = (
        db.session.execute(db.select(License).where(License.is_active == True))
        .scalars()
        .all()
    )

    total_videos = db.session.execute(db.select(db.func.count(Video.id))).scalar() or 0

    total_size = (
        db.session.execute(db.select(db.func.sum(Video.file_size))).scalar() or 0
    )

    # Get client video counts
    client_data = []
    for client in clients:
        video_count = (
            db.session.execute(
                db.select(db.func.count(Video.id)).where(Video.client_id == client.id)
            ).scalar()
            or 0
        )

        storage = (
            db.session.execute(
                db.select(db.func.sum(Video.file_size)).where(
                    Video.client_id == client.id
                )
            ).scalar()
            or 0
        )

        client_data.append(
            {
                "machine_id": client.machine_id,
                "video_count": video_count,
                "total_size": storage,
                "last_seen": client.last_seen,
            }
        )

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
    if filter_action:
        log_query = log_query.where(AuditLog.action == filter_action)

    # Fetch all matching logs (before pagination) so we can resolve and filter machine_id
    logs_raw = (
        db.session.execute(log_query).scalars().all()
    )

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

    # Filter by machine_id BEFORE pagination so counts are correct (#11 fix)
    if filter_machine_id:
        log_data = [
            l
            for l in log_data
            if l["machine_id"] and filter_machine_id.lower() in l["machine_id"].lower()
        ]

    total_logs = len(log_data)
    total_pages = max(1, (total_logs + per_page - 1) // per_page)
    log_data = log_data[offset : offset + per_page]

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
