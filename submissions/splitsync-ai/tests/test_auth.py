"""Unit tests for SplitSync AI authentication and password verification."""

import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent / "src" / "backend"
sys.path.insert(0, str(backend_dir))

from auth.service import auth_service  # noqa: E402


class TestAuthService:
    """Test suite for authentication hashing and token security."""

    def test_password_hashing_and_verification(self):
        """Verify bcrypt password hashing produces unique salted hashes and verifies accurately."""
        password = "SecurePassword123!"
        hashed = auth_service.hash_password(password)

        assert hashed != password
        assert hashed.startswith("$2b$")
        assert auth_service.verify_password(password, hashed) is True
        assert auth_service.verify_password("WrongPassword!", hashed) is False

    def test_token_creation_and_decoding(self):
        """Verify JWT token encode and decode roundtrip."""
        user_id = "test-user-uuid-123"
        email = "test@splitsync.ai"

        token = auth_service.create_token(user_id=user_id, email=email)
        assert isinstance(token, str)
        assert len(token) > 20

        payload = auth_service.decode_token(token)
        assert payload["sub"] == user_id
        assert payload["email"] == email
        assert "exp" in payload
        assert "iat" in payload
