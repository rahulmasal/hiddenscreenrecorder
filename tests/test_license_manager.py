"""
Tests for License Manager module
"""

import json
import base64
from datetime import datetime, timedelta, timezone

import pytest

# Import from shared module
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from license_manager import LicenseManager, MachineIdentifier


class TestLicenseManager:
    """Test cases for LicenseManager class"""

    @pytest.fixture
    def key_pair(self):
        """Generate a fresh RSA key pair for each test"""
        return LicenseManager.generate_key_pair()

    @pytest.fixture
    def manager_with_keys(self, key_pair):
        """Create a LicenseManager with loaded keys"""
        private_key_pem, public_key_pem = key_pair
        manager = LicenseManager()
        manager.load_private_key(private_key_pem)
        manager.load_public_key(public_key_pem)
        return manager

    @pytest.fixture
    def test_machine_id(self):
        """Return a test machine ID"""
        return "test_machine_1234567890abcdef"

    def test_generate_key_pair(self):
        """Test RSA key pair generation"""
        private_key, public_key = LicenseManager.generate_key_pair()

        # Verify keys are strings
        assert isinstance(private_key, str)
        assert isinstance(public_key, str)

        # Verify keys start with proper PEM headers
        assert private_key.startswith("-----BEGIN PRIVATE KEY-----")
        assert private_key.endswith("-----END PRIVATE KEY-----\n")
        assert public_key.startswith("-----BEGIN PUBLIC KEY-----")
        assert public_key.endswith("-----END PUBLIC KEY-----\n")

        # Verify keys are different
        assert private_key != public_key

    def test_generate_fernet_key(self):
        """Test Fernet key generation"""
        key = LicenseManager.generate_fernet_key()

        # Verify key is a string
        assert isinstance(key, str)

        # Verify key is valid base64
        try:
            base64.urlsafe_b64decode(key)
        except Exception:
            pytest.fail("Generated Fernet key is not valid base64")

    def test_load_private_key(self, key_pair):
        """Test loading private key from PEM string"""
        private_key_pem, _ = key_pair
        manager = LicenseManager()
        manager.load_private_key(private_key_pem)

        assert manager.private_key is not None

    def test_load_public_key(self, key_pair):
        """Test loading public key from PEM string"""
        _, public_key_pem = key_pair
        manager = LicenseManager()
        manager.load_public_key(public_key_pem)

        assert manager.public_key is not None

    def test_generate_license_without_private_key(self, test_machine_id):
        """Test that license generation fails without private key"""
        manager = LicenseManager()

        with pytest.raises(ValueError, match="Private key required"):
            manager.generate_license(test_machine_id)

    def test_generate_license_basic(self, manager_with_keys, test_machine_id):
        """Test basic license generation"""
        license_str = manager_with_keys.generate_license(test_machine_id)

        # Verify license is a string
        assert isinstance(license_str, str)

        # Verify license is valid base64
        try:
            license_bytes = base64.b64decode(license_str)
            license_obj = json.loads(license_bytes.decode())
        except Exception:
            pytest.fail("Generated license is not valid base64 JSON")

        # Verify license structure
        assert "data" in license_obj
        assert "signature" in license_obj

        # Verify license data structure
        license_data = license_obj["data"]
        assert "machine_id" in license_data
        assert "issued_at" in license_data
        assert "expires_at" in license_data
        assert "features" in license_data
        assert "nonce" in license_data

        # Verify machine ID matches
        assert license_data["machine_id"] == test_machine_id

    def test_generate_license_with_expiry(self, manager_with_keys, test_machine_id):
        """Test license generation with custom expiry days"""
        expiry_days = 30
        license_str = manager_with_keys.generate_license(
            test_machine_id, expiry_days=expiry_days
        )

        # Decode and verify expiry
        license_bytes = base64.b64decode(license_str)
        license_obj = json.loads(license_bytes.decode())
        license_data = license_obj["data"]

        expires_at = datetime.fromisoformat(license_data["expires_at"])
        issued_at = datetime.fromisoformat(license_data["issued_at"])

        # Verify expiry is approximately correct (within 1 second)
        expected_expiry = issued_at + timedelta(days=expiry_days)
        time_diff = abs((expires_at - expected_expiry).total_seconds())
        assert time_diff < 1

    def test_generate_license_with_features(self, manager_with_keys, test_machine_id):
        """Test license generation with custom features"""
        features = {
            "recording": True,
            "upload": False,
            "streaming": True,
        }
        license_str = manager_with_keys.generate_license(
            test_machine_id, features=features
        )

        # Decode and verify features
        license_bytes = base64.b64decode(license_str)
        license_obj = json.loads(license_bytes.decode())
        license_data = license_obj["data"]

        assert license_data["features"] == features

    def test_generate_license_default_features(
        self, manager_with_keys, test_machine_id
    ):
        """Test license generation with default features"""
        license_str = manager_with_keys.generate_license(test_machine_id)

        # Decode and verify features
        license_bytes = base64.b64decode(license_str)
        license_obj = json.loads(license_bytes.decode())
        license_data = license_obj["data"]

        assert license_data["features"] == {"recording": True, "upload": True}

    def test_generate_license_unique_nonce(self, manager_with_keys, test_machine_id):
        """Test that each license has a unique nonce"""
        license1 = manager_with_keys.generate_license(test_machine_id)
        license2 = manager_with_keys.generate_license(test_machine_id)

        # Decode both licenses
        license1_bytes = base64.b64decode(license1)
        license1_obj = json.loads(license1_bytes.decode())
        license2_bytes = base64.b64decode(license2)
        license2_obj = json.loads(license2_bytes.decode())

        # Verify nonces are different
        assert license1_obj["data"]["nonce"] != license2_obj["data"]["nonce"]


class TestLicenseValidation:
    """Test cases for license validation"""

    @pytest.fixture
    def key_pair(self):
        """Generate a fresh RSA key pair for each test"""
        return LicenseManager.generate_key_pair()

    @pytest.fixture
    def manager_with_keys(self, key_pair):
        """Create a LicenseManager with loaded keys"""
        private_key_pem, public_key_pem = key_pair
        manager = LicenseManager()
        manager.load_private_key(private_key_pem)
        manager.load_public_key(public_key_pem)
        return manager

    @pytest.fixture
    def test_machine_id(self):
        """Return a test machine ID"""
        return "test_machine_1234567890abcdef"

    def test_validate_license_without_public_key(self):
        """Test that license validation fails without public key"""
        manager = LicenseManager()

        with pytest.raises(ValueError, match="Public key required"):
            manager.validate_license("some_license_string")

    def test_validate_valid_license(self, manager_with_keys, test_machine_id):
        """Test validation of a valid license"""
        # Generate a license
        license_str = manager_with_keys.generate_license(test_machine_id)

        # Create a new manager with only public key for validation
        validator = LicenseManager()
        _, public_key_pem = LicenseManager.generate_key_pair()
        validator.load_public_key(public_key_pem)

        # Try to validate (should fail because keys don't match)
        is_valid, result = validator.validate_license(license_str, test_machine_id)

        # This should fail because we're using different keys
        assert is_valid is False
        assert "Invalid license signature" in result

    def test_validate_license_correct_keys(self, key_pair, test_machine_id):
        """Test validation of a valid license with correct keys"""
        private_key_pem, public_key_pem = key_pair

        # Generate license with private key
        generator = LicenseManager()
        generator.load_private_key(private_key_pem)
        license_str = generator.generate_license(test_machine_id)

        # Validate with public key
        validator = LicenseManager()
        validator.load_public_key(public_key_pem)
        is_valid, result = validator.validate_license(license_str, test_machine_id)

        assert is_valid is True
        assert isinstance(result, dict)
        assert result["machine_id"] == test_machine_id

    def test_validate_expired_license(self, key_pair, test_machine_id):
        """Test validation of an expired license"""
        private_key_pem, public_key_pem = key_pair

        # Generate license that expires immediately
        generator = LicenseManager()
        generator.load_private_key(private_key_pem)

        # Manually create an expired license
        license_data = {
            "machine_id": test_machine_id,
            "issued_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
            "expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            "features": {"recording": True, "upload": True},
            "nonce": "test_nonce",
        }

        # Sign the license
        license_json = json.dumps(license_data, sort_keys=True)
        signature = generator.private_key.sign(
            license_json.encode(),
            __import__("cryptography").hazmat.primitives.asymmetric.padding.PSS(
                mgf=__import__(
                    "cryptography"
                ).hazmat.primitives.asymmetric.padding.MGF1(
                    __import__("cryptography").hazmat.primitives.hashes.SHA256()
                ),
                salt_length=__import__(
                    "cryptography"
                ).hazmat.primitives.asymmetric.padding.PSS.MAX_LENGTH,
            ),
            __import__("cryptography").hazmat.primitives.hashes.SHA256(),
        )

        final_license = {
            "data": license_data,
            "signature": base64.b64encode(signature).decode(),
        }

        license_str = base64.b64encode(json.dumps(final_license).encode()).decode()

        # Validate with public key
        validator = LicenseManager()
        validator.load_public_key(public_key_pem)
        is_valid, result = validator.validate_license(license_str, test_machine_id)

        assert is_valid is False
        assert "expired" in result.lower()

    def test_validate_license_wrong_machine_id(self, key_pair, test_machine_id):
        """Test validation fails with wrong machine ID"""
        private_key_pem, public_key_pem = key_pair

        # Generate license for one machine
        generator = LicenseManager()
        generator.load_private_key(private_key_pem)
        license_str = generator.generate_license(test_machine_id)

        # Try to validate with different machine ID
        validator = LicenseManager()
        validator.load_public_key(public_key_pem)
        is_valid, result = validator.validate_license(
            license_str, "different_machine_id"
        )

        assert is_valid is False
        assert "not valid for this machine" in result.lower()

    def test_validate_corrupted_license(self, manager_with_keys):
        """Test validation of a corrupted license"""
        # Try to validate corrupted data
        is_valid, result = manager_with_keys.validate_license("not_a_valid_license")

        assert is_valid is False
        assert "error" in result.lower() or "invalid" in result.lower()

    def test_validate_tampered_license(self, key_pair, test_machine_id):
        """Test validation of a tampered license"""
        private_key_pem, public_key_pem = key_pair

        # Generate a valid license
        generator = LicenseManager()
        generator.load_private_key(private_key_pem)
        license_str = generator.generate_license(test_machine_id)

        # Tamper with the license by modifying the base64 string
        license_bytes = base64.b64decode(license_str)
        license_obj = json.loads(license_bytes.decode())

        # Modify the machine ID in the data
        license_obj["data"]["machine_id"] = "tampered_machine_id"

        # Re-encode without re-signing
        tampered_license_str = base64.b64encode(
            json.dumps(license_obj).encode()
        ).decode()

        # Validate with public key
        validator = LicenseManager()
        validator.load_public_key(public_key_pem)
        is_valid, result = validator.validate_license(
            tampered_license_str, test_machine_id
        )

        assert is_valid is False
        assert "signature" in result.lower() or "invalid" in result.lower()


class TestLicenseInfo:
    """Test cases for license info extraction"""

    @pytest.fixture
    def key_pair(self):
        """Generate a fresh RSA key pair for each test"""
        return LicenseManager.generate_key_pair()

    @pytest.fixture
    def manager_with_keys(self, key_pair):
        """Create a LicenseManager with loaded keys"""
        private_key_pem, public_key_pem = key_pair
        manager = LicenseManager()
        manager.load_private_key(private_key_pem)
        manager.load_public_key(public_key_pem)
        return manager

    @pytest.fixture
    def test_machine_id(self):
        """Return a test machine ID"""
        return "test_machine_1234567890abcdef"

    def test_get_license_info_valid(self, manager_with_keys, test_machine_id):
        """Test getting info from a valid license"""
        license_str = manager_with_keys.generate_license(test_machine_id)

        info = manager_with_keys.get_license_info(license_str)

        assert info is not None
        assert info["machine_id"] == test_machine_id
        assert "issued_at" in info
        assert "expires_at" in info
        assert "features" in info

    def test_get_license_info_invalid(self, manager_with_keys):
        """Test getting info from an invalid license string"""
        info = manager_with_keys.get_license_info("not_a_valid_license")

        assert info is None

    def test_get_license_info_corrupted(self, manager_with_keys):
        """Test getting info from corrupted license data"""
        # Create corrupted license string
        corrupted = base64.b64encode(b"not json").decode()

        info = manager_with_keys.get_license_info(corrupted)

        assert info is None


class TestMachineIdentifier:
    """Test cases for MachineIdentifier class"""

    def test_get_machine_id(self):
        """Test machine ID generation"""
        machine_id = MachineIdentifier.get_machine_id()

        # Verify it's a string
        assert isinstance(machine_id, str)

        # Verify it's a hex string (SHA256 hash)
        assert len(machine_id) == 32
        try:
            int(machine_id, 16)
        except ValueError:
            pytest.fail("Machine ID is not a valid hex string")

    def test_get_machine_id_consistent(self):
        """Test that machine ID is consistent across calls"""
        id1 = MachineIdentifier.get_machine_id()
        id2 = MachineIdentifier.get_machine_id()

        assert id1 == id2

    def test_get_system_info(self):
        """Test system info retrieval"""
        info = MachineIdentifier.get_system_info()

        # Verify it's a dictionary
        assert isinstance(info, dict)

        # Verify expected keys exist
        assert "os" in info
        assert "os_version" in info
        assert "computer_name" in info
        assert "username" in info

        # Verify values are strings
        for key, value in info.items():
            assert isinstance(value, str), f"Value for {key} should be a string"
