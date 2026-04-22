# Dockerfile for Screen Recorder Server
# Multi-stage build for optimized image size

# Stage 1: Build dependencies
FROM python:3.11-slim as builder

WORKDIR /build

# Install system dependencies for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY server/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Production image
FROM python:3.11-slim

WORKDIR /app

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local

# Copy application code (server + shared module)
COPY server/ .
COPY shared/ ./shared/

# Create necessary directories with proper permissions
RUN mkdir -p /app/data /app/uploads /app/uploads/thumbnails /app/licenses /app/keys \
    && chown -R appuser:appuser /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_APP=app.py \
    FLASK_ENV=production \
    PORT=5000 \
    HOST=0.0.0.0 \
    DATABASE_URL=sqlite:///data/screenrecorder.db \
    UPLOAD_FOLDER=/app/uploads \
    LICENSE_FOLDER=/app/licenses \
    KEYS_FOLDER=/app/keys
# NOTE: SECRET_KEY and ADMIN_PASSWORD must be set at runtime via
# docker-compose.yml or `docker run -e`. No insecure defaults are baked in.

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/v1/health', timeout=5)" || exit 1

# Switch to non-root user
USER appuser

# Run the application with gunicorn (production WSGI server)
# Falls back to Flask dev server if gunicorn is not installed
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "app:app"]
