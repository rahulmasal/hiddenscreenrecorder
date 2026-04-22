<div align="center">

# 🎬 ShadowCap

### _Capture the Unseen_

**Enterprise-grade silent screen recording with license-secured activation & auto-upload**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/License-RSA%202048-green?style=flat-square&logo=key&logoColor=white)](https://cryptography.io)

[🚀 Quick Start](#-quick-start) • [📖 Docs](#-documentation) • [🏗️ Architecture](#-architecture) • [⚙️ Setup](#-installation) • [🐳 Docker](#-docker-deployment) • [🧪 Testing](#-testing)

</div>

---

## ✨ What is ShadowCap?

ShadowCap is a **client-server screen recording platform** that runs invisibly on Windows machines, captures screen activity in configurable chunks, and automatically uploads recordings to a centralized server — all secured by **RSA-2048 license keys** bound to individual machines.

> 💡 Think of it as a **silent DVR for your fleet of Windows machines** — records everything, stores it centrally, and only authorized machines can participate.

### 🎯 Why ShadowCap?

| Problem                        | ShadowCap's Answer                                                 |
| ------------------------------ | ------------------------------------------------------------------ |
| Need invisible monitoring?     | Runs as a **hidden Windows service** — no UI, no tray icon         |
| Want only authorized machines? | **RSA-2048 signed licenses** bound to machine IDs                  |
| Worried about network drops?   | **Offline queue** with exponential backoff retry                   |
| Need multi-monitor support?    | Select any monitor or **custom screen region**                     |
| Want audio too?                | Optional **system audio / microphone capture**                     |
| Storage concerns?              | Built-in **FFmpeg video compression** with quality presets         |
| Need real-time status?         | **WebSocket live updates** + heartbeat monitoring                  |
| Managing many machines?        | **Admin dashboard** — clients, licenses, videos, logs in one place |

---

## 🌟 Feature Highlights

### 🎥 Recording Engine

- **Silent operation** — hidden Windows service, zero user interaction
- **Multi-monitor** — pick any connected display or record a custom region
- **Chunked recording** — configurable duration (default: 1-minute segments)
- **Pause / Resume** — pause recording without stopping the session
- **Audio capture** — optional microphone or system audio (WAV)
- **Video compression** — FFmpeg or OpenCV fallback with CRF quality control

### 🔐 Security & Licensing

- **RSA-2048 signed licenses** — can't be forged or tampered with
- **Machine-bound activation** — each license tied to a unique hardware ID
- **License expiration** — automatic expiry with configurable duration
- **CSRF protection** — all admin forms secured with tokens
- **Timing-attack resistant** — constant-time password comparison
- **Rate limiting** — API + login endpoints protected from brute force

### ☁️ Server & Upload

- **Auto-upload** — videos uploaded immediately after each chunk
- **Offline queue** — videos queued locally when server is unreachable
- **Exponential backoff** — intelligent retry with jitter (1s → 5min)
- **Heartbeat** — periodic server check-in for live status monitoring
- **Video streaming** — HTTP Range support for partial content / seeking
- **Thumbnail generation** — auto-extracted via FFmpeg or OpenCV

### 📊 Admin Dashboard

- **Live client status** — online/offline with last-seen timestamps
- **License management** — generate, view, and revoke licenses
- **Video browser** — stream, download, or delete recordings per client
- **Activity logs** — filterable audit trail with pagination
- **24h summary** — uploads, heartbeats, and errors at a glance

---

## 🏗️ Architecture

```
┌──────────────────────────┐              ┌──────────────────────────┐
│      CLIENT (Windows)    │              │      SERVER (Linux/Win)  │
│                          │              │                          │
│  ┌────────────────────┐  │   HTTP/S     │  ┌────────────────────┐  │
│  │   ShadowCap Agent  │  │  ──────────► │  │   Flask Server     │  │
│  │                    │  │   Upload     │  │                    │  │
│  │  • Screen Capture  │  │   Heartbeat  │  │  • REST API v1     │  │
│  │  • Audio Record    │  │   License    │  │  • Admin Dashboard │  │
│  │  • Video Compress  │  │   Validate   │  │  • Video Streaming │  │
│  │  • Offline Queue   │  │              │  │  • WebSocket Hub   │  │
│  │  • License Check   │  │              │  └────────┬───────────┘  │
│  └────────────────────┘  │              │           │              │
│                          │              │  ┌────────▼───────────┐  │
│  ┌────────────────────┐  │              │  │   SQLite Database  │  │
│  │  license.key       │  │              │  │   • Clients        │  │
│  │  (RSA-2048 bound)  │  │              │  │   • Licenses       │  │
│  └────────────────────┘  │              │  │   • Videos         │  │
│                          │              │  │   • Audit Logs     │  │
│  ┌────────────────────┐  │              │  └────────────────────┘  │
│  │  Offline Storage   │  │              │                          │
│  │  %APPDATA%/        │  │              │  ┌────────────────────┐  │
│  │  ScreenRecSvc/     │  │              │  │   Upload Storage   │  │
│  │  ├── recordings/   │  │              │  │   uploads/         │  │
│  │  ├── offline_queue/│  │              │  │   thumbnails/      │  │
│  │  └── thumbnails/   │  │              │  └────────────────────┘  │
│  └────────────────────┘  │              │                          │
└──────────────────────────┘              └──────────────────────────┘
```

---

## 🚀 Quick Start

### Server (2 minutes)

```bash
# 1. Clone & enter the project
git clone https://github.com/your-org/shadowcap.git
cd shadowcap

# 2. Set up the server
cd server
pip install -r requirements.txt
cp .env.example .env          # Edit with your passwords!

# 3. Launch
python app.py
# ✅ Server running at http://localhost:5000
# ✅ Admin dashboard at http://localhost:5000/admin
# ✅ RSA keys auto-generated on first run
```

### Client (3 minutes)

```bash
# 1. Get the machine ID
python get_machine_id.py
# → Your Machine ID: a1b2c3d4e5f6...

# 2. Generate a license on the admin dashboard
#    http://server-ip:5000/admin → Generate License → Enter Machine ID

# 3. Save the license key as license.key next to the client script

# 4. Configure & run
cd client
pip install -r requirements.txt
python screen_recorder.py
# ✅ Recording started silently
```

---

## 📖 Documentation

| Document                                               | Description                     |
| ------------------------------------------------------ | ------------------------------- |
| [🚀 Quick Start Guide](QUICK_START_GUIDE.md)           | Get running in 10 minutes       |
| [🖥️ Server Installation](SERVER_INSTALLATION_GUIDE.md) | Detailed server setup           |
| [💻 Client Installation](CLIENT_INSTALLATION_GUIDE.md) | Detailed client setup           |
| [📡 API Reference](API.md)                             | Complete REST API docs          |
| [🔄 Workflow](WORKFLOW.md)                             | How the system works end-to-end |

---

## ⚙️ Installation

### Prerequisites

| Component       | Requirement                             |
| --------------- | --------------------------------------- |
| **Python**      | 3.11 or higher                          |
| **OS (Client)** | Windows 10/11                           |
| **OS (Server)** | Windows, Linux, or macOS                |
| **FFmpeg**      | Optional — for compression & thumbnails |
| **PyAudio**     | Optional — for audio recording          |

### Server Setup

<details>
<summary>📦 Direct Installation</summary>

```bash
cd server
pip install -r requirements.txt
cp .env.example .env
# Edit .env — set ADMIN_PASSWORD and SECRET_KEY
python app.py
```

</details>

<details>
<summary>🐳 Docker Deployment</summary>

```bash
# Set required environment variables
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
export ADMIN_PASSWORD="your-secure-password"

# Launch
docker compose up -d

# Check health
curl http://localhost:5000/api/v1/health
```

</details>

### Client Setup

<details>
<summary>💻 Standard Installation</summary>

```bash
cd client
pip install -r requirements.txt

# Create config.json in the ScreenRecSvc directory
# (auto-created on first run with defaults)

# Run
python screen_recorder.py
```

</details>

<details>
<summary>🔧 Windows Service (NSSM)</summary>

```batch
:: Install as a Windows service (runs invisibly)
install_client_service.bat

:: Uninstall
uninstall_client_service.bat
```

</details>

<details>
<summary>📦 Build Standalone EXE</summary>

```bash
python build_client.py
# Output: dist/ScreenRecorder.exe (self-contained, no Python needed)
```

</details>

---

## 🎮 Client Configuration

Create `config.json` in the client's data directory:

```json
{
  "server_url": "http://YOUR_SERVER_IP:5000",
  "recording_fps": 10,
  "chunk_duration": 60,
  "heartbeat_interval": 60,
  "monitor_selection": 1,
  "region_x": 0,
  "region_y": 0,
  "region_width": 0,
  "region_height": 0,
  "enable_audio": false,
  "enable_compression": true,
  "use_websocket": false
}
```

| Parameter             | Default | Description                 |
| --------------------- | ------- | --------------------------- |
| `recording_fps`       | 10      | Frames per second           |
| `chunk_duration`      | 60      | Seconds per video file      |
| `heartbeat_interval`  | 60      | Seconds between heartbeats  |
| `monitor_selection`   | 1       | Monitor index (1 = primary) |
| `region_width/height` | 0       | 0 = full screen             |
| `enable_audio`        | false   | Record audio                |
| `enable_compression`  | true    | Compress with FFmpeg        |
| `use_websocket`       | false   | Real-time WebSocket updates |

---

## 🐳 Docker Deployment

```yaml
# docker-compose.yml (simplified)
services:
  server:
    build:
      context: .
      dockerfile: server/Dockerfile
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
      - ./uploads:/app/uploads
      - ./licenses:/app/licenses
      - ./keys:/app/keys
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - ADMIN_PASSWORD=${ADMIN_PASSWORD}
    healthcheck:
      test:
        [
          "CMD",
          "python",
          "-c",
          "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/v1/health')",
        ]
      interval: 30s
```

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=shared --cov=server

# Run specific test categories
pytest tests/ -v -m "not screen_capture and not audio and not network"
```

| Marker                        | Purpose                   |
| ----------------------------- | ------------------------- |
| `@pytest.mark.screen_capture` | Requires display hardware |
| `@pytest.mark.audio`          | Requires audio hardware   |
| `@pytest.mark.network`        | Requires network access   |
| `@pytest.mark.slow`           | Long-running tests        |

---

## 📁 Project Structure

```
ShadowCap/
├── client/                     # 🖥️ Client (Windows agent)
│   ├── screen_recorder.py      # Main recorder — capture, upload, license
│   ├── audio_recorder.py       # Audio recording module
│   ├── video_compressor.py     # FFmpeg / OpenCV compression
│   ├── monitor_manager.py      # Multi-monitor detection & selection
│   └── requirements.txt        # Python dependencies
│
├── server/                     # ☁️ Server (Flask API + Dashboard)
│   ├── app.py                  # Flask application & admin routes
│   ├── config.py               # Pydantic Settings configuration
│   ├── models.py               # SQLAlchemy database models
│   ├── auth.py                 # JWT auth, CSRF, rate limiting
│   ├── validators.py           # Input validation utilities
│   ├── video_processor.py      # Thumbnail generation
│   ├── websocket_manager.py    # Socket.IO real-time updates
│   ├── health_monitor.py       # System health checks
│   ├── logging_config.py       # Structured & colored logging
│   ├── Dockerfile              # Multi-stage Docker build
│   ├── routes/
│   │   └── api.py              # REST API v1 endpoints
│   ├── templates/              # Jinja2 HTML templates
│   └── migrations/             # Alembic database migrations
│
├── shared/                     # 🤝 Shared modules
│   ├── license_manager.py      # RSA license generation & validation
│   └── exceptions.py           # Custom exception hierarchy
│
├── tests/                      # 🧪 Test suite
│   ├── conftest.py             # Pytest fixtures & configuration
│   ├── test_license_manager.py # License system tests
│   └── test_validators.py      # Input validation tests
│
├── docker-compose.yml          # Docker Compose orchestration
├── nginx.conf                  # Nginx reverse proxy config
├── build_client.py             # PyInstaller build script
└── pytest.ini                  # Pytest configuration
```

---

## 🔒 Security Model

```
                    ┌─────────────────────────────────┐
                    │         LICENSE FLOW             │
                    └─────────────────────────────────┘

  Server                              Client
  ──────                              ──────
  1. Generate RSA-2048 key pair
  2. Store private_key.pem (server)
  3. Embed public_key.pem (client)

  4. Admin generates license:
     ├── Machine ID from client
     ├── Expiry date
     ├── Feature flags
     └── Sign with private key → license.key

                                     5. Load license.key
                                     6. Verify signature (public key)
                                     7. Check expiration
                                     8. Verify machine ID match
                                     9. ✅ Start recording
                                        ❌ Exit silently
```

---

## 🛡️ Security Features

- ✅ RSA-2048 PSS signature with SHA-256 for license signing
- ✅ Constant-time password comparison (timing attack prevention)
- ✅ CSRF tokens on all state-changing requests
- ✅ Rate limiting on API and login endpoints
- ✅ Security headers (X-Frame-Options, HSTS, X-Content-Type-Options)
- ✅ HTTPS enforcement via Flask-Talisman (optional)
- ✅ Input validation with path traversal prevention
- ✅ Secure filename handling
- ✅ Session regeneration on authentication

---

## 📊 API Endpoints

| Method | Endpoint                         | Auth    | Description                  |
| ------ | -------------------------------- | ------- | ---------------------------- |
| `POST` | `/api/v1/upload`                 | License | Upload video recording       |
| `POST` | `/api/v1/validate-license`       | —       | Validate a license key       |
| `POST` | `/api/v1/heartbeat`              | License | Client heartbeat             |
| `GET`  | `/api/v1/health`                 | —       | Server health check          |
| `GET`  | `/api/v1/stream/<id>/<file>`     | —       | Stream video (Range support) |
| `GET`  | `/api/v1/thumbnail/<id>/<file>`  | —       | Get video thumbnail          |
| `GET`  | `/api/v1/video-info/<id>/<file>` | —       | Video metadata               |
| `GET`  | `/api/v1/get-machine-id`         | —       | Get machine identifier       |
| `GET`  | `/api/v1/get-public-key`         | —       | Get server public key        |

> 📖 Full API documentation: [API.md](API.md)

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📝 License

This project is proprietary software. All rights reserved.

---

<div align="center">

**ShadowCap** — _Capture the Unseen_

Made with 🖤 for enterprise monitoring

</div>
