"""Tests for trusted proxy IP extraction in authentication rate limiting."""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.auth_rate_limit import get_client_ip, _is_valid_ip
from app.config import Settings


class TestTrustedProxyIP(unittest.IsolatedAsyncioTestCase):
    """Tests for get_client_ip with trusted proxy configuration."""

    def setUp(self) -> None:
        # Clear any settings cache
        pass

    def _make_request(self, headers: dict = None, client_host: str = "192.168.1.1") -> MagicMock:
        """Create a mock FastAPI Request object."""
        request = MagicMock()
        request.headers = headers or {}
        request.client = MagicMock()
        request.client.host = client_host
        return request

    async def test_direct_request_no_trusted_proxy(self) -> None:
        """Direct request without trusted proxy config should use immediate peer."""
        request = self._make_request(headers={"X-Forwarded-For": "10.0.0.1, 192.168.1.100"}, client_host="192.168.1.100")

        with patch("app.core.auth_rate_limit.get_settings") as mock_settings:
            mock_settings.return_value = Settings(trusted_proxy_count=0)
            ip = await get_client_ip(request)
            self.assertEqual(ip, "192.168.1.100")

    async def test_direct_request_with_xff_but_no_trusted_proxy(self) -> None:
        """X-Forwarded-For should be ignored when trusted_proxy_count=0."""
        request = self._make_request(headers={"X-Forwarded-For": "10.0.0.1, 192.168.1.100"}, client_host="192.168.1.100")

        with patch("app.core.auth_rate_limit.get_settings") as mock_settings:
            mock_settings.return_value = Settings(trusted_proxy_count=0)
            ip = await get_client_ip(request)
            self.assertEqual(ip, "192.168.1.100")

    async def test_trusted_proxy_one_hop(self) -> None:
        """With trusted_proxy_count=1, use the single IP in X-Forwarded-For (client)."""
        # Single trusted proxy (load balancer): XFF contains only the client IP
        request = self._make_request(headers={"X-Forwarded-For": "10.0.0.1"}, client_host="192.168.1.100")

        with patch("app.core.auth_rate_limit.get_settings") as mock_settings:
            mock_settings.return_value = Settings(trusted_proxy_count=1)
            ip = await get_client_ip(request)
            self.assertEqual(ip, "10.0.0.1")

    async def test_trusted_proxy_two_hops(self) -> None:
        """With trusted_proxy_count=2, use the leftmost of two IPs in X-Forwarded-For."""
        # Two trusted proxies: XFF contains client and first proxy
        request = self._make_request(headers={"X-Forwarded-For": "10.0.0.1, 192.168.1.50"}, client_host="192.168.1.100")

        with patch("app.core.auth_rate_limit.get_settings") as mock_settings:
            mock_settings.return_value = Settings(trusted_proxy_count=2)
            ip = await get_client_ip(request)
            self.assertEqual(ip, "10.0.0.1")

    async def test_trusted_proxy_count_exceeds_ips(self) -> None:
        """When trusted_proxy_count exceeds number of IPs, fall back to immediate peer."""
        request = self._make_request(headers={"X-Forwarded-For": "10.0.0.1"}, client_host="192.168.1.100")

        with patch("app.core.auth_rate_limit.get_settings") as mock_settings:
            mock_settings.return_value = Settings(trusted_proxy_count=3)
            ip = await get_client_ip(request)
            self.assertEqual(ip, "192.168.1.100")

    async def test_missing_xff_header(self) -> None:
        """Missing X-Forwarded-For should fall back to immediate peer."""
        request = self._make_request(headers={}, client_host="192.168.1.100")

        with patch("app.core.auth_rate_limit.get_settings") as mock_settings:
            mock_settings.return_value = Settings(trusted_proxy_count=1)
            ip = await get_client_ip(request)
            self.assertEqual(ip, "192.168.1.100")

    async def test_malformed_xff_header(self) -> None:
        """Malformed X-Forwarded-For should fall back to immediate peer."""
        request = self._make_request(headers={"X-Forwarded-For": "not-an-ip, also-bad"}, client_host="192.168.1.100")

        with patch("app.core.auth_rate_limit.get_settings") as mock_settings:
            mock_settings.return_value = Settings(trusted_proxy_count=1)
            ip = await get_client_ip(request)
            self.assertEqual(ip, "192.168.1.100")

    async def test_invalid_ip_in_xff(self) -> None:
        """Invalid IP in X-Forwarded-For should fall back to immediate peer."""
        request = self._make_request(headers={"X-Forwarded-For": "not-an-ip, 192.168.1.100"}, client_host="192.168.1.100")

        with patch("app.core.auth_rate_limit.get_settings") as mock_settings:
            mock_settings.return_value = Settings(trusted_proxy_count=1)
            ip = await get_client_ip(request)
            self.assertEqual(ip, "192.168.1.100")

    async def test_spoofed_xff_from_untrusted_client(self) -> None:
        """Spoofed X-Forwarded-For from untrusted client should be ignored when no trusted proxy."""
        request = self._make_request(headers={"X-Forwarded-For": "10.0.0.1"}, client_host="192.168.1.100")

        with patch("app.core.auth_rate_limit.get_settings") as mock_settings:
            mock_settings.return_value = Settings(trusted_proxy_count=0)
            ip = await get_client_ip(request)
            self.assertEqual(ip, "192.168.1.100")

    async def test_ipv6_addresses(self) -> None:
        """IPv6 addresses should be handled correctly."""
        request = self._make_request(headers={"X-Forwarded-For": "2001:db8::1"}, client_host="2001:db8::2")

        with patch("app.core.auth_rate_limit.get_settings") as mock_settings:
            mock_settings.return_value = Settings(trusted_proxy_count=1)
            ip = await get_client_ip(request)
            self.assertEqual(ip, "2001:db8::1")

    async def test_client_none_fallback(self) -> None:
        """When request.client is None, return 'unknown'."""
        request = MagicMock()
        request.headers = {}
        request.client = None

        with patch("app.core.auth_rate_limit.get_settings") as mock_settings:
            mock_settings.return_value = Settings(trusted_proxy_count=0)
            ip = await get_client_ip(request)
            self.assertEqual(ip, "unknown")

    async def test_xff_with_whitespace(self) -> None:
        """X-Forwarded-For with whitespace should be parsed correctly."""
        request = self._make_request(headers={"X-Forwarded-For": "10.0.0.1"}, client_host="192.168.1.100")

        with patch("app.core.auth_rate_limit.get_settings") as mock_settings:
            mock_settings.return_value = Settings(trusted_proxy_count=1)
            ip = await get_client_ip(request)
            self.assertEqual(ip, "10.0.0.1")


class TestIsValidIP(unittest.TestCase):
    """Tests for _is_valid_ip helper function."""

    def test_valid_ipv4(self) -> None:
        self.assertTrue(_is_valid_ip("192.168.1.1"))
        self.assertTrue(_is_valid_ip("10.0.0.1"))
        self.assertTrue(_is_valid_ip("172.16.0.1"))
        self.assertTrue(_is_valid_ip("0.0.0.0"))
        self.assertTrue(_is_valid_ip("255.255.255.255"))

    def test_invalid_ipv4(self) -> None:
        self.assertFalse(_is_valid_ip("256.1.1.1"))
        self.assertFalse(_is_valid_ip("192.168.1"))
        self.assertFalse(_is_valid_ip("192.168.1.1.1"))
        self.assertFalse(_is_valid_ip("not-an-ip"))
        self.assertFalse(_is_valid_ip(""))

    def test_valid_ipv6(self) -> None:
        self.assertTrue(_is_valid_ip("2001:db8::1"))
        self.assertTrue(_is_valid_ip("::1"))
        self.assertTrue(_is_valid_ip("fe80::1%lo0"))

    def test_invalid_ipv6(self) -> None:
        self.assertFalse(_is_valid_ip("not-ipv6"))
        self.assertFalse(_is_valid_ip("gggg::1"))

    def test_edge_cases(self) -> None:
        self.assertFalse(_is_valid_ip(""))
        self.assertFalse(_is_valid_ip("x" * 50))  # Too long


if __name__ == "__main__":
    unittest.main()