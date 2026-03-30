"""
Custom exceptions for the Screen Recorder Application
"""

from typing import Optional, Dict, Any


class ScreenRecorderError(Exception):
    """Base exception for all screen recorder errors"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON responses"""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


class LicenseError(ScreenRecorderError):
    """License validation or processing error"""

    pass


class LicenseExpiredError(LicenseError):
    """License has expired"""

    def __init__(self, expires_at: str, message: Optional[str] = None):
        if message is None:
            message = f"License expired on {expires_at}"
        super().__init__(message, {"expires_at": expires_at})


class LicenseInvalidError(LicenseError):
    """License key is invalid or corrupted"""

    def __init__(self, reason: str, message: Optional[str] = None):
        if message is None:
            message = f"Invalid license: {reason}"
        super().__init__(message, {"reason": reason})


class LicenseMachineMismatchError(LicenseError):
    """License machine ID doesn't match current machine"""

    def __init__(self, expected_id: str, actual_id: str, message: Optional[str] = None):
        if message is None:
            message = "License machine ID mismatch"
        super().__init__(message, {"expected": expected_id, "actual": actual_id})


class UploadError(ScreenRecorderError):
    """Video upload error"""

    pass


class UploadFailedError(UploadError):
    """Video upload failed"""

    def __init__(self, filename: str, reason: str, status_code: Optional[int] = None):
        message = f"Upload failed for {filename}: {reason}"
        details = {"filename": filename, "reason": reason}
        if status_code:
            details["status_code"] = status_code
        super().__init__(message, details)


class UploadSizeExceededError(UploadError):
    """Video file size exceeds maximum allowed"""

    def __init__(self, filename: str, size: int, max_size: int):
        message = (
            f"File {filename} size ({size} bytes) exceeds maximum ({max_size} bytes)"
        )
        super().__init__(
            message, {"filename": filename, "size": size, "max_size": max_size}
        )


class SessionError(ScreenRecorderError):
    """Windows session error"""

    pass


class SessionZeroError(SessionError):
    """Running in Windows Session 0 (service context)"""

    def __init__(self, message: Optional[str] = None):
        if message is None:
            message = "Screen capture not available in Windows Session 0"
        super().__init__(message, {"session_id": 0})


class SessionRelaunchError(SessionError):
    """Failed to relaunch in user session"""

    def __init__(self, reason: str, message: Optional[str] = None):
        if message is None:
            message = f"Failed to relaunch in user session: {reason}"
        super().__init__(message, {"reason": reason})


class RecordingError(ScreenRecorderError):
    """Screen recording error"""

    pass


class RecordingStartError(RecordingError):
    """Failed to start recording"""

    def __init__(self, reason: str, message: Optional[str] = None):
        if message is None:
            message = f"Failed to start recording: {reason}"
        super().__init__(message, {"reason": reason})


class RecordingStopError(RecordingError):
    """Failed to stop recording gracefully"""

    def __init__(self, reason: str, message: Optional[str] = None):
        if message is None:
            message = f"Failed to stop recording: {reason}"
        super().__init__(message, {"reason": reason})


class VideoWriterError(RecordingError):
    """Video writer initialization or operation error"""

    def __init__(self, filepath: str, reason: str, message: Optional[str] = None):
        if message is None:
            message = f"Video writer error for {filepath}: {reason}"
        super().__init__(message, {"filepath": filepath, "reason": reason})


class AudioError(ScreenRecorderError):
    """Audio recording error"""

    pass


class AudioInitializationError(AudioError):
    """Failed to initialize audio recording"""

    def __init__(self, reason: str, message: Optional[str] = None):
        if message is None:
            message = f"Audio initialization failed: {reason}"
        super().__init__(message, {"reason": reason})


class AudioDeviceError(AudioError):
    """Audio device error"""

    def __init__(self, device_name: str, reason: str, message: Optional[str] = None):
        if message is None:
            message = f"Audio device error ({device_name}): {reason}"
        super().__init__(message, {"device": device_name, "reason": reason})


class ConfigurationError(ScreenRecorderError):
    """Configuration error"""

    pass


class ConfigurationLoadError(ConfigurationError):
    """Failed to load configuration"""

    def __init__(self, config_path: str, reason: str, message: Optional[str] = None):
        if message is None:
            message = f"Failed to load config from {config_path}: {reason}"
        super().__init__(message, {"config_path": config_path, "reason": reason})


class ConfigurationValidationError(ConfigurationError):
    """Configuration validation failed"""

    def __init__(
        self, field: str, value: Any, reason: str, message: Optional[str] = None
    ):
        if message is None:
            message = f"Invalid configuration for {field}: {reason}"
        super().__init__(message, {"field": field, "value": value, "reason": reason})


class NetworkError(ScreenRecorderError):
    """Network communication error"""

    pass


class ServerUnreachableError(NetworkError):
    """Server is unreachable"""

    def __init__(self, server_url: str, reason: str, message: Optional[str] = None):
        if message is None:
            message = f"Server unreachable at {server_url}: {reason}"
        super().__init__(message, {"server_url": server_url, "reason": reason})


class RateLimitExceededError(NetworkError):
    """API rate limit exceeded"""

    def __init__(self, endpoint: str, retry_after: Optional[int] = None):
        message = f"Rate limit exceeded for {endpoint}"
        details = {"endpoint": endpoint}
        if retry_after:
            details["retry_after"] = retry_after
        super().__init__(message, details)


class DatabaseError(ScreenRecorderError):
    """Database operation error"""

    pass


class DatabaseConnectionError(DatabaseError):
    """Database connection failed"""

    def __init__(self, reason: str, message: Optional[str] = None):
        if message is None:
            message = f"Database connection failed: {reason}"
        super().__init__(message, {"reason": reason})


class DatabaseQueryError(DatabaseError):
    """Database query failed"""

    def __init__(self, query: str, reason: str, message: Optional[str] = None):
        if message is None:
            message = f"Database query failed: {reason}"
        super().__init__(message, {"query": query[:100], "reason": reason})


class ValidationError(ScreenRecorderError):
    """Input validation error"""

    pass


class InvalidFilenameError(ValidationError):
    """Invalid filename (potential path traversal)"""

    def __init__(self, filename: str, message: Optional[str] = None):
        if message is None:
            message = f"Invalid filename: {filename}"
        super().__init__(message, {"filename": filename})


class InvalidMachineIDError(ValidationError):
    """Invalid machine ID format"""

    def __init__(self, machine_id: str, message: Optional[str] = None):
        if message is None:
            message = f"Invalid machine ID format: {machine_id}"
        super().__init__(message, {"machine_id": machine_id})


class InvalidLicenseKeyError(ValidationError):
    """Invalid license key format"""

    def __init__(self, reason: str, message: Optional[str] = None):
        if message is None:
            message = f"Invalid license key: {reason}"
        super().__init__(message, {"reason": reason})


class CompressionError(ScreenRecorderError):
    """Video compression error"""

    pass


class FFmpegNotFoundError(CompressionError):
    """FFmpeg executable not found"""

    def __init__(self, ffmpeg_path: str, message: Optional[str] = None):
        if message is None:
            message = f"FFmpeg not found at {ffmpeg_path}"
        super().__init__(message, {"ffmpeg_path": ffmpeg_path})


class CompressionFailedError(CompressionError):
    """Video compression failed"""

    def __init__(self, input_path: str, reason: str, message: Optional[str] = None):
        if message is None:
            message = f"Compression failed for {input_path}: {reason}"
        super().__init__(message, {"input_path": input_path, "reason": reason})


class MonitorError(ScreenRecorderError):
    """Monitor detection or capture error"""

    pass


class MonitorNotFoundError(MonitorError):
    """Specified monitor not found"""

    def __init__(
        self, monitor_index: int, available_monitors: int, message: Optional[str] = None
    ):
        if message is None:
            message = (
                f"Monitor {monitor_index} not found (available: {available_monitors})"
            )
        super().__init__(
            message, {"requested": monitor_index, "available": available_monitors}
        )


class MonitorCaptureError(MonitorError):
    """Failed to capture from monitor"""

    def __init__(self, monitor_index: int, reason: str, message: Optional[str] = None):
        if message is None:
            message = f"Monitor {monitor_index} capture failed: {reason}"
        super().__init__(message, {"monitor": monitor_index, "reason": reason})
