"""Tests for CORS origin validation in production configuration."""
import os
import pytest
from app.config import Settings, _validate_cors_origins, _validate_cors_origin


class TestCorsOriginValidation:
    """Tests for CORS origin validation."""

    def test_valid_https_origin_in_production(self) -> None:
        """Valid HTTPS origin should pass in production."""
        errors = _validate_cors_origins("https://app.arqau.com", "production")
        assert errors == []

    def test_multiple_valid_https_origins_in_production(self) -> None:
        """Multiple valid HTTPS origins should pass in production."""
        errors = _validate_cors_origins("https://app.arqau.com,https://admin.arqau.com", "production")
        assert errors == []

    def test_missing_cors_origins_in_production(self) -> None:
        """Missing CORS_ORIGINS should fail in production."""
        errors = _validate_cors_origins("", "production")
        assert "CORS_ORIGINS must contain at least one origin" in errors

    def test_wildcard_origin_rejected_in_production(self) -> None:
        """Wildcard origin should be rejected in production."""
        errors = _validate_cors_origins("*", "production")
        assert any("wildcard" in e.lower() for e in errors)

    def test_localhost_origin_rejected_in_production(self) -> None:
        """Localhost origin should be rejected in production."""
        errors = _validate_cors_origins("http://localhost:3000", "production")
        assert any("localhost" in e.lower() for e in errors)

    def test_http_origin_rejected_in_production(self) -> None:
        """HTTP origin should be rejected in production."""
        errors = _validate_cors_origins("http://app.arqau.com", "production")
        assert any("https" in e.lower() for e in errors)

    def test_malformed_origin_rejected_in_production(self) -> None:
        """Malformed origin should be rejected in production."""
        errors = _validate_cors_origins("not-a-url", "production")
        assert any("scheme and host" in e.lower() for e in errors)

    def test_origin_with_path_rejected_in_production(self) -> None:
        """Origin with path should be rejected in production."""
        errors = _validate_cors_origins("https://app.arqau.com/path", "production")
        assert any("path" in e.lower() for e in errors)

    def test_origin_with_query_rejected_in_production(self) -> None:
        """Origin with query string should be rejected in production."""
        errors = _validate_cors_origins("https://app.arqau.com?foo=bar", "production")
        assert any("query" in e.lower() for e in errors)

    def test_origin_with_fragment_rejected_in_production(self) -> None:
        """Origin with fragment should be rejected in production."""
        errors = _validate_cors_origins("https://app.arqau.com#section", "production")
        assert any("fragment" in e.lower() for e in errors)

    def test_origin_with_credentials_rejected_in_production(self) -> None:
        """Origin with credentials should be rejected in production."""
        errors = _validate_cors_origins("https://user:pass@app.arqau.com", "production")
        assert any("credential" in e.lower() for e in errors)

    def test_valid_localhost_in_development(self) -> None:
        """Localhost HTTP should be allowed in development."""
        errors = _validate_cors_origins("http://localhost:3000", "development")
        assert errors == []

    def test_valid_localhost_in_testing(self) -> None:
        """Localhost HTTP should be allowed in testing."""
        errors = _validate_cors_origins("http://localhost:3000", "testing")
        assert errors == []

    def test_non_localhost_http_rejected_in_development(self) -> None:
        """Non-localhost HTTP should be rejected in development."""
        errors = _validate_cors_origins("http://app.arqau.com", "development")
        assert any("https" in e.lower() or "localhost" in e.lower() for e in errors)

    def test_localhost_rejected_in_production(self) -> None:
        """Localhost should be rejected in production."""
        errors = _validate_cors_origins("https://localhost", "production")
        assert any("localhost" in e.lower() for e in errors)

    def test_127_0_0_1_rejected_in_production(self) -> None:
        """127.0.0.1 should be rejected in production."""
        errors = _validate_cors_origins("https://127.0.0.1", "production")
        assert any("localhost" in e.lower() for e in errors)

    def test_settings_validates_cors_in_production(self) -> None:
        """Settings should validate CORS in production."""
        with pytest.raises(ValueError, match="CORS"):
            Settings(
                environment="production",
                cors_origins="http://localhost:3000",
                secret_key="a" * 32,
                jwt_issuer="arqau",
                jwt_audience="arqau-api",
                database_url="postgresql://user:pass@localhost/db",
                openai_api_key="test-key",
            )

    def test_settings_accepts_valid_cors_in_production(self) -> None:
        """Settings should accept valid CORS in production."""
        settings = Settings(
            environment="production",
            cors_origins="https://app.arqau.com",
            secret_key="a" * 32,
            jwt_issuer="arqau",
            jwt_audience="arqau-api",
            database_url="postgresql://user:pass@localhost/db",
            openai_api_key="test-key",
        )
        assert settings.cors_origins_list == ["https://app.arqau.com"]

    def test_settings_accepts_multiple_origins_in_production(self) -> None:
        """Settings should accept multiple valid origins in production."""
        settings = Settings(
            environment="production",
            cors_origins="https://app.arqau.com,https://admin.arqau.com",
            secret_key="a" * 32,
            jwt_issuer="arqau",
            jwt_audience="arqau-api",
            database_url="postgresql://user:pass@localhost/db",
            openai_api_key="test-key",
        )
        assert settings.cors_origins_list == ["https://app.arqau.com", "https://admin.arqau.com"]


class TestCorsOriginValidationEdgeCases:
    """Edge case tests for CORS origin validation."""

    def test_origin_with_trailing_slash(self) -> None:
        """Origin with trailing slash should be accepted (normalized by CORS)."""
        errors = _validate_cors_origins("https://app.arqau.com/", "production")
        assert errors == []

    def test_origin_with_port(self) -> None:
        """Origin with explicit port should be accepted if valid HTTPS."""
        errors = _validate_cors_origins("https://app.arqau.com:443", "production")
        assert errors == []

    def test_origin_with_non_standard_port(self) -> None:
        """Origin with non-standard port should be accepted if valid HTTPS."""
        errors = _validate_cors_origins("https://app.arqau.com:8443", "production")
        assert errors == []

    def test_ipv6_loopback_rejected_in_production(self) -> None:
        """IPv6 loopback should be rejected in production."""
        errors = _validate_cors_origins("https://[::1]", "production")
        assert any("localhost" in e.lower() for e in errors)

    def test_0_0_0_0_rejected_in_production(self) -> None:
        """0.0.0.0 should be rejected in production."""
        errors = _validate_cors_origins("https://0.0.0.0", "production")
        assert any("localhost" in e.lower() for e in errors)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])