"""
RedirectResolver (spec section 17) — resolves tracking/redirect URLs found
in job-alert emails down to the final job posting URL, with SSRF protection.

This never uses a browser — it's a bounded-hop HTTPX HEAD/GET chase with
strict validation of every hop's target before the request is made.
"""

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.config.settings import Settings, get_settings

_BLOCKED_HOSTNAMES = {
    "localhost",
    "0.0.0.0",
}  # noqa: S104 - literal blocklist entry, not a bind address


@dataclass(frozen=True)
class RedirectResolutionResult:
    final_url: str
    hops: int
    blocked: bool
    reason: str | None = None


class SSRFError(Exception):
    pass


class RedirectResolver:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def resolve(self, url: str) -> RedirectResolutionResult:
        current = url
        hops = 0

        try:
            while hops < self._settings.redirect_max_hops:
                self._validate_url_is_safe(current)

                response = httpx.get(
                    current,
                    follow_redirects=False,
                    timeout=self._settings.redirect_timeout_seconds,
                )

                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        break
                    current = str(httpx.URL(current).join(location))
                    hops += 1
                    continue

                break

            self._validate_url_is_safe(current)
            return RedirectResolutionResult(final_url=current, hops=hops, blocked=False)

        except SSRFError as exc:
            return RedirectResolutionResult(final_url=url, hops=hops, blocked=True, reason=str(exc))
        except httpx.HTTPError as exc:
            return RedirectResolutionResult(
                final_url=current, hops=hops, blocked=False, reason=f"request failed: {exc}"
            )

    def _validate_url_is_safe(self, url: str) -> None:
        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            raise SSRFError(f"Rejected non-HTTP(S) scheme: {parsed.scheme!r}")

        hostname = parsed.hostname
        if not hostname:
            raise SSRFError("URL has no hostname")

        if hostname.lower() in _BLOCKED_HOSTNAMES:
            raise SSRFError(f"Rejected blocked hostname: {hostname}")

        try:
            resolved_ip = ipaddress.ip_address(socket.gethostbyname(hostname))
        except (socket.gaierror, ValueError) as exc:
            raise SSRFError(f"Could not resolve hostname: {hostname}") from exc

        if (
            resolved_ip.is_loopback
            or resolved_ip.is_private
            or resolved_ip.is_link_local
            or resolved_ip.is_reserved
            or resolved_ip.is_multicast
        ):
            raise SSRFError(f"Rejected internal/private address: {resolved_ip}")
