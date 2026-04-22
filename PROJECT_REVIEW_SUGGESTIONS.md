# Screen Recorder App — Comprehensive Project Review & Suggestions

> **Reviewed:** 2026-04-22 | **Files analyzed:** 30+ across client, server, shared, tests, and infrastructure

---

## 🔴 Critical Issues (Fix Immediately)

### 1. Security: Templates Embedded in Python Code

**File:** [`server/app.py`](server/app.py:145) — `create_templates()` function (lines 145–680)

Over 500 lines of HTML templates are stored as string literals inside `app.py` and **overwritten to disk on every startup** (line 671). This:

- Makes templates impossible to audit for XSS/injection
- Creates a race condition for template injection attacks
- Destroys any manual template customizations on restart
- Bloats `app.py` to 1094 lines

**Fix:** Move all templates to the existing [`server/templates/`](server/templates/) directory as proper `.html` files. Remove `create_templates()` entirely. Use Jinja2 template inheritance to reduce duplication (every template repeats the same navbar).

---

### 2. Security: CORS Wide Open

**File:** [`server/app.py`](server/app.py:63) — `CORS(app)`

CORS is enabled with **no origin restrictions**, allowing any website to make requests to your server.

**Fix:**

```python
CORS(app, origins=["https://your-domain.com"], supports_credentials=True)
```

---

### 3. Security: WebSocket CORS Set to `*`

**File:** [`server/websocket_manager.py`](server/websocket_manager.py:63) — `cors_allowed_origins="*"`

Same issue as above for WebSocket connections.

**Fix:** Restrict to known origins or make it configurable via [`settings`](server/config.py:13).

---

### 4. Security: Video Streaming & Thumbnails Have No Authentication

**File:** [`server/routes/api.py`](server/routes/api.py:463) — `stream_video()` and [`api.py`](server/routes/api.py:558) — `get_thumbnail()`

Anyone who knows a `machine_id` and `filename` can stream videos and access thumbnails without any authentication. This is a **data exfiltration risk**.

**Fix:** Add `@require_auth` or implement token-based temporary access URLs (signed URLs with expiry).

---

### 5. Security: Admin Logout via GET Request

**File:** [`server/app.py`](server/app.py:709) — `admin_logout()`

GET requests for logout are vulnerable to CSRF attacks (e.g., an image tag `<img src="/admin/logout">`).

**Fix:** Change to POST with CSRF token:

```python
@app.route("/admin/logout", methods=["POST"])
@require_csrf
def admin_logout():
```

---

### 6. Security: Insecure Defaults in Docker

**File:** [`server/Dockerfile`](server/Dockerfile:45) and [`docker-compose.yml`](docker-compose.yml:18)

Hardcoded insecure defaults:

```
SECRET_KEY=change-this-to-a-secure-random-string-in-production
ADMIN_PASSWORD=change-this-to-a-secure-password-in-production
```

**Fix:** Remove defaults from Dockerfile. In `docker-compose.yml`, fail startup if `SECRET_KEY` and `ADMIN_PASSWORD` are not set:

```yaml
environment:
  - SECRET_KEY=${SECRET_KEY:?SECRET_KEY must be set}
  - ADMIN_PASSWORD=${ADMIN_PASSWORD:?ADMIN_PASSWORD must be set}
```

---

### 7. Security: Private Key Stored Unencrypted

**File:** [`shared/license_manager.py`](shared/license_manager.py:44) — `serialization.NoEncryption()`

The RSA private key is stored on disk with no encryption. Anyone with file access can generate licenses.

**Fix:** Encrypt the private key with a passphrase loaded from environment variable:

```python
encryption_algorithm=serialization.BestAvailableEncryption(passphrase.encode())
```

---

## 🟠 High Priority Issues

### 8. Architecture: Monolithic `app.py` (1094 lines)

**File:** [`server/app.py`](server/app.py:1)

Contains templates, admin routes, key management, and initialization all in one file.

**Fix:**

- Move admin routes to `server/routes/admin.py` as a Blueprint
- Move key management to `server/key_manager.py`
- Templates should be proper files in `templates/` (see issue #1)

---

### 9. Architecture: Monolithic `screen_recorder.py` (1726 lines)

**File:** [`client/screen_recorder.py`](client/screen_recorder.py:1)

Contains `Config`, `RetryHandler`, `OfflineQueue`, `HeartbeatManager`, `ScreenRecorder`, `HiddenRunner`, and more.

**Fix:** Split into modules:

```
client/
  config.py          # Config dataclass
  retry_handler.py   # RetryHandler
  offline_queue.py   # OfflineQueue
  heartbeat.py       # HeartbeatManager
  recorder.py        # ScreenRecorder
  hidden_runner.py   # HiddenRunner
  main.py            # Entry point
```

---

### 10. Performance: N+1 Query Problem in Dashboard

**File:** [`server/app.py`](server/app.py:743) — `admin_dashboard()`

For each client, separate queries are executed for `video_count` and `storage`:

```python
for client in clients:
    video_count = db.session.execute(...).scalar()  # N+1!
    storage = db.session.execute(...).scalar()       # N+1!
```

**Fix:** Use a single aggregated query:

```python
from sqlalchemy import func
stats = db.session.query(
    Video.client_id,
    func.count(Video.id).label('video_count'),
    func.sum(Video.file_size).label('total_size')
).group_by(Video.client_id).all()
```

---

### 11. Performance: Logs Page Loads ALL Records Then Filters in Python

**File:** [`server/app.py`](server/app.py:1026) — `admin_logs()`

All audit logs are fetched from the database, then filtered by `machine_id` in Python:

```python
logs_raw = db.session.execute(log_query).scalars().all()  # ALL logs!
# ... then filter in Python
if filter_machine_id:
    log_data = [l for l in log_data if ...]
```

**Fix:** Add `machine_id` column to `AuditLog` model and filter in SQL with proper database-level pagination.

---

### 12. Performance: LicenseManager Instantiated Per Request

**File:** [`server/routes/api.py`](server/routes/api.py:149) and [`api.py`](server/routes/api.py:307)

A new `LicenseManager()` is created and the public key is loaded from disk on **every request**:

```python
lm = LicenseManager()
with open(public_key_path, "r") as f:
    lm.load_public_key(f.read())
```

**Fix:** Use the already-initialized `license_manager` from [`app.py`](server/app.py:138) or cache it at module level.

---

### 13. Database: SQLite Not Suitable for Production

**File:** [`server/config.py`](server/config.py:39) — `database_url: str = Field(default="sqlite:///screenrecorder.db")`

SQLite doesn't handle concurrent writes well. With multiple upload clients, you'll get `database is locked` errors.

**Fix:** Support PostgreSQL for production:

```python
database_url: str = Field(default="sqlite:///screenrecorder.db", alias="DATABASE_URL")
```

Add `psycopg2-binary` to requirements and update Docker Compose with a PostgreSQL service.

---

### 14. Database: `db.create_all()` Conflicts with Flask-Migrate

**File:** [`server/models.py`](server/models.py:172) — `init_db()`

Both `db.create_all()` and Flask-Migrate are used, which can conflict:

```python
if not (len(sys.argv) > 1 and sys.argv[1] == 'db'):
    with app.app_context():
        db.create_all()
```

**Fix:** Remove `db.create_all()` and rely solely on Flask-Migrate for schema management. Use migrations for all schema changes.

---

### 15. Rate Limiting: In-Memory Only, Not Production-Ready

**File:** [`server/auth.py`](server/auth.py:193) — `rate_limit()`

The rate limiter uses an in-memory dictionary, which:

- Doesn't work across multiple workers/processes
- Is lost on server restart
- Can be bypassed by restarting the server

**Fix:** Use `Flask-Limiter` with Redis backend for production:

```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
limiter = Limiter(app, key_func=get_remote_address, storage_uri="redis://localhost:6379")
```

---

### 16. No Production WSGI Server Configuration

**File:** [`server/app.py`](server/app.py:1088)

Uses Flask's development server (`app.run()`). While `gunicorn` is in [`requirements.txt`](server/requirements.txt:9), there's no gunicorn config.

**Fix:** Add `gunicorn.conf.py`:

```python
bind = "0.0.0.0:5000"
workers = 4
worker_class = "gthread"
threads = 2
timeout = 120
```

Update `CMD` in Dockerfile to use gunicorn.

---

## 🟡 Medium Priority Issues

### 17. Inconsistent Datetime Handling

**Files:** Multiple

Mix of deprecated `datetime.utcnow()` and correct `datetime.now(timezone.utc)`:

- [`server/websocket_manager.py`](server/websocket_manager.py:30): `datetime.utcnow` (deprecated in Python 3.12)
- [`server/logging_config.py`](server/logging_config.py:23): `datetime.utcnow()`
- [`server/models.py`](server/models.py:24): `datetime.now(timezone.utc)` ✓

**Fix:** Replace all `datetime.utcnow()` with `datetime.now(timezone.utc)` consistently.

---

### 18. Duplicate Code: PasswordSecurity vs AuthManager

**File:** [`server/auth.py`](server/auth.py:35) — `PasswordSecurity` and [`auth.py`](server/auth.py:88) — `AuthManager`

Both classes have `hash_password()` and `verify_password()` methods with overlapping logic.

**Fix:** Remove `AuthManager.hash_password()` and `AuthManager.verify_password()`, delegate to `PasswordSecurity` static methods.

---

### 19. No Log Rotation

**Files:** [`client/screen_recorder.py`](client/screen_recorder.py:104), [`server/logging_config.py`](server/logging_config.py:124)

Log files grow indefinitely with no rotation.

**Fix:** Use `RotatingFileHandler`:

```python
from logging.handlers import RotatingFileHandler
handler = RotatingFileHandler('app.log', maxBytes=10*1024*1024, backupCount=5)
```

---

### 20. No Audit Log Cleanup/Retention Policy

**File:** [`server/models.py`](server/models.py:125) — `AuditLog`

Audit logs grow indefinitely. The `admin_logs` page will become slower over time.

**Fix:** Add a configurable retention period and a cleanup job:

```python
# In config.py
audit_log_retention_days: int = Field(default=90)

# Periodic cleanup
cutoff = datetime.now(timezone.utc) - timedelta(days=settings.audit_log_retention_days)
db.session.execute(db.delete(AuditLog).where(AuditLog.timestamp < cutoff))
```

---

### 21. No Video Cleanup Policy

No mechanism to automatically delete old videos when disk space is low.

**Fix:** Add configurable retention policy and disk-space-based cleanup in the health monitor or a background task.

---

### 22. `os` Module Imported Twice in `screen_recorder.py`

**File:** [`client/screen_recorder.py`](client/screen_recorder.py:8) and [`screen_recorder.py`](client/screen_recorder.py:134)

```python
import os  # line 8
import os  # line 134 (inside try block)
```

**Fix:** Remove the duplicate import on line 134.

---

### 23. Test Machine ID Doesn't Match Validator Pattern

**File:** [`tests/conftest.py`](tests/conftest.py:44) — `test_machine_id = "test_machine_id_1234567890abcdef"`

Contains underscores, but [`validators.py`](server/validators.py:23) requires `^[a-fA-F0-9]{32,64}$`. Tests using this ID would fail real validation.

**Fix:** Use a valid hex string:

```python
test_machine_id = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
```

---

### 24. Very Limited Test Coverage

**Files:** [`tests/`](tests/)

Only 2 test files exist: `test_license_manager.py` and `test_validators.py`. No tests for:

- Server API routes (upload, heartbeat, streaming)
- Authentication & session management
- Client code (recording, offline queue, retry logic)
- Video processing
- Admin dashboard

**Fix:** Add test files:

```
tests/
  test_api.py            # API route tests with Flask test client
  test_auth.py           # Authentication tests
  test_models.py         # Database model tests
  test_offline_queue.py  # Offline queue tests
  test_retry_handler.py  # Retry logic tests
```

---

### 25. Shared Module Path Manipulation is Fragile

**Files:** [`server/app.py`](server/app.py:18), [`server/routes/api.py`](server/routes/api.py:22), [`client/screen_recorder.py`](client/screen_recorder.py:77)

All three files manually manipulate `sys.path` to find the shared module:

```python
_shared_paths = [os.path.join(..., "shared"), os.path.join(..., "..", "shared")]
for _shared_path in _shared_paths:
    if os.path.isdir(_shared_path):
        sys.path.insert(0, _shared_path)
```

**Fix:** Create a proper Python package with `pyproject.toml` and install in editable mode:

```bash
pip install -e .
```

---

### 26. No Disk Space Check Before Recording (Client)

**File:** [`client/screen_recorder.py`](client/screen_recorder.py:524) — `ScreenRecorder`

The client starts recording without checking available disk space, which can fill up the disk.

**Fix:** Add a pre-recording disk space check:

```python
import shutil
usage = shutil.disk_usage(self.video_dir)
if usage.free < 100 * 1024 * 1024:  # Less than 100MB
    logger.error("Insufficient disk space for recording")
    return False
```

---

### 27. Config Serialization Leaks Internal State

**File:** [`client/screen_recorder.py`](client/screen_recorder.py:269) — `Config.save_to_file()`

```python
json.dump(self.__dict__, f, indent=2)
```

This serializes ALL attributes including any private ones added at runtime.

**Fix:** Use `dataclasses.asdict()` or explicitly list serializable fields.

---

## 🔵 Low Priority / Improvements

### 28. Add Content Security Policy Header

**File:** [`server/app.py`](server/app.py:98) — `add_security_headers()`

CSP header is commented out:

```python
# response.headers['Content-Security-Policy'] = "default-src 'self'"
```

**Fix:** Enable with appropriate directives for Bootstrap CDN:

```python
response.headers['Content-Security-Policy'] = (
    "default-src 'self'; "
    "style-src 'self' https://cdn.jsdelivr.net; "
    "script-src 'self' https://cdn.jsdelivr.net"
)
```

---

### 29. Add Pagination to Admin Dashboard

**File:** [`server/app.py`](server/app.py:718) — `admin_dashboard()`

All clients and licenses are loaded without pagination. Will be slow with many clients.

**Fix:** Add pagination similar to the logs page.

---

### 30. Docker Compose: Add Resource Limits

**File:** [`docker-compose.yml`](docker-compose.yml:1)

No memory/CPU limits on the container.

**Fix:**

```yaml
deploy:
  resources:
    limits:
      memory: 2G
      cpus: "2.0"
```

---

### 31. Docker Compose: Add PostgreSQL Service

**File:** [`docker-compose.yml`](docker-compose.yml:1)

For production, add a PostgreSQL service instead of SQLite.

**Fix:**

```yaml
postgres:
  image: postgres:16-alpine
  environment:
    POSTGRES_DB: screenrecorder
    POSTGRES_USER: ${DB_USER}
    POSTGRES_PASSWORD: ${DB_PASSWORD}
  volumes:
    - pgdata:/var/lib/postgresql/data
  networks:
    - screenrecorder
```

---

### 32. Add CI/CD Pipeline

No CI/CD configuration exists (no GitHub Actions, etc.).

**Fix:** Add `.github/workflows/ci.yml`:

```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r server/requirements.txt
      - run: pip install -r shared/requirements.txt 2>/dev/null || true
      - run: pip install pytest
      - run: pytest tests/ -v
```

---

### 33. Remove `nssm.exe` from Repository

**File:** [`nssm.exe`](nssm.exe)

Binary executable committed to the repository is a security and licensing concern.

**Fix:** Download `nssm.exe` at install time from the official source, or reference it as an external dependency.

---

### 34. Add `.env` to `.gitignore`

Ensure `.env` files are never committed:

**Fix:** Verify `.gitignore` contains:

```
.env
server/.env
*.key
*.pem
```

---

### 35. No Bandwidth Throttling for Uploads

**File:** [`client/screen_recorder.py`](client/screen_recorder.py:1)

Uploads can consume all available bandwidth, impacting the user's network.

**Fix:** Add configurable upload speed limit using `requests` with chunked transfer and sleep.

---

### 36. Add Two-Factor Authentication for Admin

**File:** [`server/auth.py`](server/auth.py:88)

Admin login is just a password. For a system managing sensitive video data, 2FA should be considered.

**Fix:** Add TOTP-based 2FA using `pyotp` library.

---

### 37. Encrypt Videos at Rest

Video files are stored unencrypted on the server. Anyone with disk access can view them.

**Fix:** Add optional AES encryption for stored videos using the `cryptography` library (already a dependency).

---

### 38. Add Health Alerting

**File:** [`server/health_monitor.py`](server/health_monitor.py:55)

Health checks exist but don't alert anyone when status is critical.

**Fix:** Add email/webhook notifications when health status changes to CRITICAL.

---

### 39. Template Duplication — Use Jinja2 Inheritance

Every HTML template repeats the same navbar, Bootstrap CDN link, and boilerplate.

**Fix:** Create a `base.html` template:

```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html>
  <head>
    <title>{% block title %}Screen Recorder{% endblock %}</title>
    <link
      href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css"
      rel="stylesheet"
    />
    {% block extra_head %}{% endblock %}
  </head>
  <body>
    <nav class="navbar navbar-dark bg-dark">
      <!-- shared navbar -->
    </nav>
    <div class="container mt-4">{% block content %}{% endblock %}</div>
  </body>
</html>
```

---

### 40. Add API Key Authentication for Programmatic Access

**File:** [`server/models.py`](server/models.py:145) — `ApiKey` model exists but is unused

The `ApiKey` model is defined but never used anywhere in the codebase.

**Fix:** Implement API key authentication for programmatic access to the API, enabling automation without admin session.

---

## 📊 Summary

| Priority    | Count | Key Areas                                              |
| ----------- | ----- | ------------------------------------------------------ |
| 🔴 Critical | 7     | Security vulnerabilities (CORS, auth, templates, keys) |
| 🟠 High     | 9     | Architecture, performance, database, rate limiting     |
| 🟡 Medium   | 11    | Code quality, testing, datetime, logging               |
| 🔵 Low      | 13    | DevOps, features, hardening                            |

### Top 5 Actions to Take First:

1. **Fix CORS** — Restrict origins in both HTTP and WebSocket
2. **Move templates out of Python** — Eliminate the template injection risk
3. **Add authentication to streaming endpoints** — Prevent unauthorized video access
4. **Fix admin logout to POST** — Prevent CSRF logout attacks
5. **Remove insecure Docker defaults** — Fail if secrets aren't set
