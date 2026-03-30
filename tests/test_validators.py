"""
Tests for Validators module
"""

import pytest

# Import from server module
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "server"))

from validators import InputValidator, validate_request_data


class TestInputValidator:
    """Test cases for InputValidator class"""

    # ==================== Machine ID Validation ====================

    def test_validate_machine_id_valid(self):
        """Test valid machine ID"""
        valid_id = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
        is_valid, error = InputValidator.validate_machine_id(valid_id)

        assert is_valid is True
        assert error is None

    def test_validate_machine_id_empty(self):
        """Test empty machine ID"""
        is_valid, error = InputValidator.validate_machine_id("")

        assert is_valid is False
        assert "required" in error.lower()

    def test_validate_machine_id_none(self):
        """Test None machine ID"""
        is_valid, error = InputValidator.validate_machine_id(None)

        assert is_valid is False
        assert "required" in error.lower()

    def test_validate_machine_id_not_string(self):
        """Test non-string machine ID"""
        is_valid, error = InputValidator.validate_machine_id(12345)

        assert is_valid is False
        assert "string" in error.lower()

    def test_validate_machine_id_too_short(self):
        """Test machine ID that's too short"""
        short_id = "abc123"
        is_valid, error = InputValidator.validate_machine_id(short_id)

        assert is_valid is False
        assert "32" in error

    def test_validate_machine_id_too_long(self):
        """Test machine ID that's too long"""
        long_id = "a" * 100
        is_valid, error = InputValidator.validate_machine_id(long_id)

        assert is_valid is False
        assert "64" in error

    def test_validate_machine_id_invalid_chars(self):
        """Test machine ID with invalid characters"""
        invalid_id = "g1h2i3j4k5l6m7n8o9p0q1r2s3t4u5v6"  # g is not valid hex
        is_valid, error = InputValidator.validate_machine_id(invalid_id)

        assert is_valid is False
        assert "hexadecimal" in error.lower()

    def test_validate_machine_id_uppercase(self):
        """Test machine ID with uppercase letters"""
        upper_id = "A1B2C3D4E5F6A7B8C9D0E1F2A3B4C5D6"
        is_valid, error = InputValidator.validate_machine_id(upper_id)

        assert is_valid is True
        assert error is None

    # ==================== License Key Validation ====================

    def test_validate_license_key_valid(self):
        """Test valid license key"""
        # Create a valid base64 string that's long enough
        import base64

        valid_key = base64.b64encode(b"test_license_data" * 10).decode()
        is_valid, error = InputValidator.validate_license_key(valid_key)

        assert is_valid is True
        assert error is None

    def test_validate_license_key_empty(self):
        """Test empty license key"""
        is_valid, error = InputValidator.validate_license_key("")

        assert is_valid is False
        assert "required" in error.lower()

    def test_validate_license_key_none(self):
        """Test None license key"""
        is_valid, error = InputValidator.validate_license_key(None)

        assert is_valid is False
        assert "required" in error.lower()

    def test_validate_license_key_not_string(self):
        """Test non-string license key"""
        is_valid, error = InputValidator.validate_license_key(12345)

        assert is_valid is False
        assert "string" in error.lower()

    def test_validate_license_key_too_short(self):
        """Test license key that's too short"""
        short_key = "abc123"
        is_valid, error = InputValidator.validate_license_key(short_key)

        assert is_valid is False
        assert "short" in error.lower()

    def test_validate_license_key_too_long(self):
        """Test license key that's too long"""
        long_key = "A" * 2001
        is_valid, error = InputValidator.validate_license_key(long_key)

        assert is_valid is False
        assert "long" in error.lower()

    def test_validate_license_key_invalid_base64(self):
        """Test license key with invalid base64"""
        invalid_key = "not_valid_base64!!!"
        is_valid, error = InputValidator.validate_license_key(invalid_key)

        assert is_valid is False
        assert "base64" in error.lower()

    # ==================== Filename Validation ====================

    def test_validate_filename_valid(self):
        """Test valid filename"""
        valid_name = "rec_20240115_103000.mp4"
        is_valid, error = InputValidator.validate_filename(valid_name)

        assert is_valid is True
        assert error is None

    def test_validate_filename_empty(self):
        """Test empty filename"""
        is_valid, error = InputValidator.validate_filename("")

        assert is_valid is False
        assert "required" in error.lower()

    def test_validate_filename_none(self):
        """Test None filename"""
        is_valid, error = InputValidator.validate_filename(None)

        assert is_valid is False
        assert "required" in error.lower()

    def test_validate_filename_not_string(self):
        """Test non-string filename"""
        is_valid, error = InputValidator.validate_filename(12345)

        assert is_valid is False
        assert "string" in error.lower()

    def test_validate_filename_path_traversal_dots(self):
        """Test filename with path traversal using dots"""
        malicious_name = "../../../etc/passwd"
        is_valid, error = InputValidator.validate_filename(malicious_name)

        assert is_valid is False
        assert "traversal" in error.lower()

    def test_validate_filename_path_traversal_slash(self):
        """Test filename with path traversal using slash"""
        malicious_name = "/etc/passwd"
        is_valid, error = InputValidator.validate_filename(malicious_name)

        assert is_valid is False
        assert "traversal" in error.lower()

    def test_validate_filename_path_traversal_backslash(self):
        """Test filename with path traversal using backslash"""
        malicious_name = "\\Windows\\System32\\config"
        is_valid, error = InputValidator.validate_filename(malicious_name)

        assert is_valid is False
        assert "traversal" in error.lower()

    def test_validate_filename_invalid_chars(self):
        """Test filename with invalid characters"""
        invalid_name = "file<script>alert('xss')</script>.mp4"
        is_valid, error = InputValidator.validate_filename(invalid_name)

        assert is_valid is False
        assert "invalid" in error.lower()

    def test_validate_filename_too_long(self):
        """Test filename that's too long"""
        long_name = "a" * 256 + ".mp4"
        is_valid, error = InputValidator.validate_filename(long_name)

        assert is_valid is False
        assert "255" in error

    def test_validate_filename_with_spaces(self):
        """Test filename with spaces (should be valid)"""
        spaced_name = "my video file.mp4"
        is_valid, error = InputValidator.validate_filename(spaced_name)

        assert is_valid is True
        assert error is None

    def test_validate_filename_with_dashes(self):
        """Test filename with dashes (should be valid)"""
        dashed_name = "rec-2024-01-15.mp4"
        is_valid, error = InputValidator.validate_filename(dashed_name)

        assert is_valid is True
        assert error is None

    def test_validate_filename_with_underscores(self):
        """Test filename with underscores (should be valid)"""
        underscored_name = "rec_20240115_103000.mp4"
        is_valid, error = InputValidator.validate_filename(underscored_name)

        assert is_valid is True
        assert error is None

    # ==================== File Extension Validation ====================

    def test_validate_file_extension_valid_mp4(self):
        """Test valid MP4 extension"""
        allowed = {"mp4", "avi", "mov", "mkv"}
        is_valid, error = InputValidator.validate_file_extension("video.mp4", allowed)

        assert is_valid is True
        assert error is None

    def test_validate_file_extension_valid_avi(self):
        """Test valid AVI extension"""
        allowed = {"mp4", "avi", "mov", "mkv"}
        is_valid, error = InputValidator.validate_file_extension("video.avi", allowed)

        assert is_valid is True
        assert error is None

    def test_validate_file_extension_invalid(self):
        """Test invalid file extension"""
        allowed = {"mp4", "avi", "mov", "mkv"}
        is_valid, error = InputValidator.validate_file_extension("video.exe", allowed)

        assert is_valid is False
        assert "not allowed" in error.lower()

    def test_validate_file_extension_no_extension(self):
        """Test filename without extension"""
        allowed = {"mp4", "avi", "mov", "mkv"}
        is_valid, error = InputValidator.validate_file_extension("video", allowed)

        assert is_valid is False
        assert "extension" in error.lower()

    def test_validate_file_extension_case_insensitive(self):
        """Test that extension check is case insensitive"""
        allowed = {"mp4", "avi", "mov", "mkv"}
        is_valid, error = InputValidator.validate_file_extension("video.MP4", allowed)

        assert is_valid is True
        assert error is None

    # ==================== Path Validation ====================

    def test_validate_path_valid(self):
        """Test valid path"""
        is_valid, error = InputValidator.validate_path("videos/my_video.mp4")

        assert is_valid is True
        assert error is None

    def test_validate_path_empty(self):
        """Test empty path"""
        is_valid, error = InputValidator.validate_path("")

        assert is_valid is False
        assert "required" in error.lower()

    def test_validate_path_none(self):
        """Test None path"""
        is_valid, error = InputValidator.validate_path(None)

        assert is_valid is False
        assert "required" in error.lower()

    def test_validate_path_not_string(self):
        """Test non-string path"""
        is_valid, error = InputValidator.validate_path(12345)

        assert is_valid is False
        assert "string" in error.lower()

    def test_validate_path_traversal(self):
        """Test path with traversal"""
        is_valid, error = InputValidator.validate_path("../../../etc/passwd")

        assert is_valid is False
        assert "traversal" in error.lower()

    def test_validate_path_with_base_dir(self, temp_dir):
        """Test path validation with base directory"""
        # Valid path within base directory
        is_valid, error = InputValidator.validate_path("videos/my_video.mp4", temp_dir)

        assert is_valid is True
        assert error is None

    def test_validate_path_outside_base_dir(self, temp_dir):
        """Test path outside base directory"""
        # Path that would escape base directory
        is_valid, error = InputValidator.validate_path("../../etc/passwd", temp_dir)

        assert is_valid is False
        assert "traversal" in error.lower() or "outside" in error.lower()

    # ==================== Expiry Days Validation ====================

    def test_validate_expiry_days_valid(self):
        """Test valid expiry days"""
        is_valid, error = InputValidator.validate_expiry_days(365)

        assert is_valid is True
        assert error is None

    def test_validate_expiry_days_minimum(self):
        """Test minimum expiry days"""
        is_valid, error = InputValidator.validate_expiry_days(1)

        assert is_valid is True
        assert error is None

    def test_validate_expiry_days_maximum(self):
        """Test maximum expiry days"""
        is_valid, error = InputValidator.validate_expiry_days(3650)

        assert is_valid is True
        assert error is None

    def test_validate_expiry_days_zero(self):
        """Test zero expiry days"""
        is_valid, error = InputValidator.validate_expiry_days(0)

        assert is_valid is False
        assert "at least 1" in error.lower()

    def test_validate_expiry_days_negative(self):
        """Test negative expiry days"""
        is_valid, error = InputValidator.validate_expiry_days(-1)

        assert is_valid is False
        assert "at least 1" in error.lower()

    def test_validate_expiry_days_too_large(self):
        """Test expiry days exceeding maximum"""
        is_valid, error = InputValidator.validate_expiry_days(3651)

        assert is_valid is False
        assert "3650" in error

    def test_validate_expiry_days_string(self):
        """Test expiry days as string (should be converted)"""
        is_valid, error = InputValidator.validate_expiry_days("365")

        assert is_valid is True
        assert error is None

    def test_validate_expiry_days_invalid_string(self):
        """Test expiry days as invalid string"""
        is_valid, error = InputValidator.validate_expiry_days("not_a_number")

        assert is_valid is False
        assert "integer" in error.lower()

    # ==================== Features Validation ====================

    def test_validate_features_valid(self):
        """Test valid features"""
        features = {"recording": True, "upload": False, "streaming": True}
        is_valid, error = InputValidator.validate_features(features)

        assert is_valid is True
        assert error is None

    def test_validate_features_not_dict(self):
        """Test features that's not a dictionary"""
        is_valid, error = InputValidator.validate_features("not a dict")

        assert is_valid is False
        assert "dictionary" in error.lower()

    def test_validate_features_unknown_feature(self):
        """Test features with unknown feature name"""
        features = {"recording": True, "unknown_feature": True}
        is_valid, error = InputValidator.validate_features(features)

        assert is_valid is False
        assert "unknown" in error.lower()

    def test_validate_features_non_boolean_value(self):
        """Test features with non-boolean value"""
        features = {"recording": "yes"}
        is_valid, error = InputValidator.validate_features(features)

        assert is_valid is False
        assert "boolean" in error.lower()

    # ==================== String Sanitization ====================

    def test_sanitize_string_normal(self):
        """Test normal string sanitization"""
        result = InputValidator.sanitize_string("  hello world  ")

        assert result == "hello world"

    def test_sanitize_string_empty(self):
        """Test empty string sanitization"""
        result = InputValidator.sanitize_string("")

        assert result == ""

    def test_sanitize_string_none(self):
        """Test None string sanitization"""
        result = InputValidator.sanitize_string(None)

        assert result == ""

    def test_sanitize_string_truncation(self):
        """Test string truncation"""
        long_string = "a" * 2000
        result = InputValidator.sanitize_string(long_string, max_length=100)

        assert len(result) == 100

    def test_sanitize_string_null_bytes(self):
        """Test removal of null bytes"""
        string_with_nulls = "hello\x00world"
        result = InputValidator.sanitize_string(string_with_nulls)

        assert "\x00" not in result
        assert result == "helloworld"

    # ==================== JSON Size Validation ====================

    def test_validate_json_size_valid(self):
        """Test valid JSON size"""
        small_data = {"key": "value"}
        is_valid, error = InputValidator.validate_json_size(small_data)

        assert is_valid is True
        assert error is None

    def test_validate_json_size_too_large(self):
        """Test JSON data that's too large"""
        large_data = {"key": "a" * 200000}  # ~200KB
        is_valid, error = InputValidator.validate_json_size(large_data, max_size_kb=100)

        assert is_valid is False
        assert "large" in error.lower()

    def test_validate_json_size_invalid_json(self):
        """Test invalid JSON data"""
        # Create an object that can't be JSON serialized
        invalid_data = {"key": object()}
        is_valid, error = InputValidator.validate_json_size(invalid_data)

        assert is_valid is False
        assert "json" in error.lower()


class TestValidateRequestData:
    """Test cases for validate_request_data function"""

    def test_validate_request_data_valid(self):
        """Test valid request data"""
        data = {"name": "test", "value": 123}
        required = ["name", "value"]
        is_valid, error = validate_request_data(data, required)

        assert is_valid is True
        assert error is None

    def test_validate_request_data_not_dict(self):
        """Test request data that's not a dictionary"""
        is_valid, error = validate_request_data("not a dict", ["field"])

        assert is_valid is False
        assert "json" in error.lower()

    def test_validate_request_data_missing_required(self):
        """Test request data with missing required field"""
        data = {"name": "test"}
        required = ["name", "value"]
        is_valid, error = validate_request_data(data, required)

        assert is_valid is False
        assert "missing" in error.lower()
        assert "value" in error.lower()

    def test_validate_request_data_empty_required(self):
        """Test request data with empty required field"""
        data = {"name": "", "value": 123}
        required = ["name", "value"]
        is_valid, error = validate_request_data(data, required)

        assert is_valid is False
        assert "empty" in error.lower()

    def test_validate_request_data_none_required(self):
        """Test request data with None required field"""
        data = {"name": None, "value": 123}
        required = ["name", "value"]
        is_valid, error = validate_request_data(data, required)

        assert is_valid is False
        assert "empty" in error.lower()

    def test_validate_request_data_with_optional(self):
        """Test request data with optional fields"""
        data = {"name": "test", "value": 123, "optional": "extra"}
        required = ["name", "value"]
        optional = ["optional"]
        is_valid, error = validate_request_data(data, required, optional)

        assert is_valid is True
        assert error is None

    def test_validate_request_data_unknown_fields(self):
        """Test request data with unknown fields"""
        data = {"name": "test", "value": 123, "unknown": "field"}
        required = ["name", "value"]
        optional = ["optional"]
        is_valid, error = validate_request_data(data, required, optional)

        assert is_valid is False
        assert "unknown" in error.lower()

    def test_validate_request_data_no_optional_list(self):
        """Test request data without optional fields list (should allow any extra)"""
        data = {"name": "test", "value": 123, "extra": "field"}
        required = ["name", "value"]
        is_valid, error = validate_request_data(data, required, optional_fields=None)

        assert is_valid is True
        assert error is None
