"""
Health Monitor Module

Provides system health checks for:
- Database connectivity
- Disk space availability
- Required dependencies
- API endpoints
"""

import logging
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class HealthStatus:
    """Health check status constants"""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class HealthCheck:
    """Represents a single health check result"""

    def __init__(
        self,
        name: str,
        status: str = HealthStatus.UNKNOWN,
        message: str = "",
        details: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.status = status
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


class HealthMonitor:
    """
    System health monitor with comprehensive checks.

    Usage:
    monitor = HealthMonitor()
    status = monitor.check_all()
    if status["overall"] != "healthy":
        handle_unhealthy_status(status)
    """

    # Disk space thresholds (percentage)
    DISK_WARNING_THRESHOLD = 80.0
    DISK_CRITICAL_THRESHOLD = 90.0

    def __init__(
        self, upload_folder: str = "instance/uploads", data_folder: str = "instance"
    ):
        self.upload_folder = Path(upload_folder)
        self.data_folder = Path(data_folder)

    def check_disk_space(self, path: Optional[Path] = None) -> HealthCheck:
        """
        Check available disk space.

        Args:
            path: Path to check (defaults to upload folder)

        Returns:
            HealthCheck with disk space status
        """
        check_path = path or self.upload_folder

        try:
            # Get disk usage statistics
            usage = shutil.disk_usage(str(check_path))
            total_gb = usage.total / (1024**3)
            free_gb = usage.free / (1024**3)
            used_percent = ((usage.total - usage.free) / usage.total) * 100

            # Determine status based on usage percentage
            if used_percent >= self.DISK_CRITICAL_THRESHOLD:
                status = HealthStatus.CRITICAL
                message = f"Critical: Disk usage at {used_percent:.1f}%"
            elif used_percent >= self.DISK_WARNING_THRESHOLD:
                status = HealthStatus.WARNING
                message = f"Warning: Disk usage at {used_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk usage OK: {used_percent:.1f}%"

            return HealthCheck(
                name="disk_space",
                status=status,
                message=message,
                details={
                    "path": str(check_path),
                    "total_gb": round(total_gb, 2),
                    "free_gb": round(free_gb, 2),
                    "used_percent": round(used_percent, 1),
                    "warning_threshold": self.DISK_WARNING_THRESHOLD,
                    "critical_threshold": self.DISK_CRITICAL_THRESHOLD,
                },
            )

        except Exception as e:
            logger.error(f"Disk space check failed: {e}")
            return HealthCheck(
                name="disk_space",
                status=HealthStatus.UNKNOWN,
                message=f"Check failed: {str(e)}",
                details={"error": str(e)},
            )

    def check_database_folder(self) -> HealthCheck:
        """
        Check if database folder is accessible.

        Returns:
            HealthCheck with database folder status
        """
        try:
            # Ensure data folder exists and is writable
            self.data_folder.mkdir(parents=True, exist_ok=True)

            # Test write access
            test_file = self.data_folder / ".health_check"
            test_file.write_text("health check")
            test_file.unlink()

            return HealthCheck(
                name="database_folder",
                status=HealthStatus.HEALTHY,
                message="Database folder accessible",
                details={
                    "path": str(self.data_folder),
                    "exists": self.data_folder.exists(),
                    "writable": self._is_writable(self.data_folder),
                },
            )

        except Exception as e:
            logger.error(f"Database folder check failed: {e}")
            return HealthCheck(
                name="database_folder",
                status=HealthStatus.CRITICAL,
                message=f"Database folder check failed: {str(e)}",
                details={"error": str(e)},
            )

    def check_dependencies(self) -> HealthCheck:
        """
        Check if required dependencies are available.

        Returns:
            HealthCheck with dependency status
        """
        missing_deps = []
        optional_deps = []

        # Check critical dependencies
        critical_modules = [
            ("flask", "Flask web framework"),
            ("sqlalchemy", "Database ORM"),
            ("cryptography", "Cryptographic functions"),
        ]

        for module, description in critical_modules:
            try:
                __import__(module.replace("-", "_"))
            except ImportError:
                missing_deps.append(f"{module} ({description})")

        # Check optional dependencies
        optional_modules = [
            ("cv2", "OpenCV (video processing)"),
            ("ffmpeg", "FFmpeg (video compression)"),
            ("pyaudio", "PyAudio (audio recording)"),
        ]

        for module, description in optional_modules:
            try:
                __import__(module.replace("-", "_"))
            except ImportError:
                optional_deps.append(f"{module} ({description})")

        # Determine status
        if missing_deps:
            status = HealthStatus.CRITICAL
            message = f"Missing critical dependencies: {', '.join(missing_deps)}"
        elif optional_deps:
            status = HealthStatus.WARNING
            message = f"Some optional dependencies missing: {', '.join(optional_deps)}"
        else:
            status = HealthStatus.HEALTHY
            message = "All dependencies available"

        return HealthCheck(
            name="dependencies",
            status=status,
            message=message,
            details={
                "missing_critical": missing_deps,
                "missing_optional": optional_deps,
            },
        )

    def check_database_connection(self, db_session) -> HealthCheck:
        """
        Check database connectivity.

        Args:
            db_session: SQLAlchemy database session

        Returns:
            HealthCheck with database connection status
        """
        try:
            # Simple query to test connection - works with both SQLAlchemy 1.x and 2.x
            from sqlalchemy import text

            db_session.execute(text("SELECT 1"))

            return HealthCheck(
                name="database_connection",
                status=HealthStatus.HEALTHY,
                message="Database connection OK",
                details={"connected": True},
            )

        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return HealthCheck(
                name="database_connection",
                status=HealthStatus.CRITICAL,
                message=f"Database connection failed: {str(e)}",
                details={"error": str(e)},
            )

    def _is_writable(self, path: Path) -> bool:
        """Check if a path is writable"""
        try:
            test_file = path / ".write_test"
            test_file.write_text("test")
            test_file.unlink()
            return True
        except (OSError, PermissionError):
            return False

    def check_all(self, db_session=None) -> Dict[str, Any]:
        """
        Run all health checks.

        Args:
            db_session: Optional database session for connectivity check

        Returns:
            Dictionary with overall status and individual check results
        """
        results = []
        overall_status = HealthStatus.HEALTHY

        # Run disk space check
        disk_result = self.check_disk_space()
        results.append(disk_result.to_dict())
        if disk_result.status == HealthStatus.CRITICAL:
            overall_status = HealthStatus.CRITICAL
        elif (
            disk_result.status == HealthStatus.WARNING
            and overall_status != HealthStatus.CRITICAL
        ):
            overall_status = HealthStatus.WARNING

        # Run database folder check
        db_folder_result = self.check_database_folder()
        results.append(db_folder_result.to_dict())
        if db_folder_result.status == HealthStatus.CRITICAL:
            overall_status = HealthStatus.CRITICAL
        elif (
            db_folder_result.status == HealthStatus.WARNING
            and overall_status != HealthStatus.CRITICAL
        ):
            overall_status = HealthStatus.WARNING

        # Run dependencies check
        deps_result = self.check_dependencies()
        results.append(deps_result.to_dict())
        if deps_result.status == HealthStatus.CRITICAL:
            overall_status = HealthStatus.CRITICAL
        elif (
            deps_result.status == HealthStatus.WARNING
            and overall_status != HealthStatus.CRITICAL
        ):
            overall_status = HealthStatus.WARNING

        # Run database connection check if session provided
        if db_session is not None:
            db_conn_result = self.check_database_connection(db_session)
            results.append(db_conn_result.to_dict())
            if db_conn_result.status == HealthStatus.CRITICAL:
                overall_status = HealthStatus.CRITICAL
            elif (
                db_conn_result.status == HealthStatus.WARNING
                and overall_status != HealthStatus.CRITICAL
            ):
                overall_status = HealthStatus.WARNING

        return {
            "overall": overall_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": results,
        }


# Global health monitor instance
health_monitor = HealthMonitor()


def get_health_status() -> Dict[str, Any]:
    """Get overall system health status"""
    return health_monitor.check_all()
