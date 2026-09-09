"""HTTP transport for fetching ЕИС public pages.

Uses httpx (already a project dependency).  No authentication,
no CAPTCHA bypass, no SOAP — plain GET requests only.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
DEFAULT_TIMEOUT_SECONDS: float = 30.0

_EIS_BASE = "https://zakupki.gov.ru"
_EIS_ORIGIN = "https://zakupki.gov.ru"

_NOTICE_PATH = "/epz/order/notice/{notice_type}/view/common-info.html"

# Only public 44-ФЗ notice types that exist on ЕИС (digital registration
# numbers are associated with one of these notice codes).
_NOTICE_TYPES_44FZ: tuple[str, ...] = (
    "ea20",
    "ea21",
    "ok1",
    "ok2",
    "za",
    "zk",
    "zz",
)

# 44-ФЗ registration numbers are long digit strings (>= 6 digits).
# Conservative format: leading digits only, no separators.
_REG_NUMBER_RE = re.compile(r"^\d{6,20}$")


def _build_notice_url_path(notice_type: str) -> str:
    return _NOTICE_PATH.format(notice_type=notice_type)


class EisTransportError(Exception):
    """Transport-level failure when fetching a ЕИС page."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code


def validate_eis_origin(url: str) -> None:
    """Validate that a URL points at the expected public ЕИС origin.

    Raises EisTransportError if the scheme/host does not match the
    single allowed HTTPS origin (https://zakupki.gov.ru), or if the URL
    contains userinfo, a port, a non-HTTPS scheme, or any loopback /
    private / alternate host.

    This prevents SSRF-style fetches of arbitrary external origins.
    """
    if not isinstance(url, str) or not url:
        raise EisTransportError("URL must be a non-empty string")

    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise EisTransportError(f"Malformed URL: {url}") from exc

    if parsed.scheme != "https":
        raise EisTransportError(
            f"Only https is allowed, got scheme {parsed.scheme!r} for {url}",
        )
    if parsed.netloc != _EIS_ORIGIN.replace("https://", ""):
        raise EisTransportError(f"Unexpected host for {url}")
    if parsed.username or parsed.password:
        raise EisTransportError(f"Userinfo is not allowed in URL: {url}")
    if parsed.port is not None:
        raise EisTransportError(f"Explicit port is not allowed in URL: {url}")


def build_notice_url(
    reg_number: str,
    *,
    notice_type: str = "ea20",
) -> str:
    """Build a full ЕИС public notice URL from a registration number.

    Validates the registration number and notice type before building.
    """
    validate_reg_number(reg_number)
    validate_notice_type(notice_type)
    path = _build_notice_url_path(notice_type)
    query = f"regNumber={reg_number}"
    return f"{_EIS_BASE}{path}?{query}"


def validate_reg_number(reg_number: str) -> None:
    """Validate a 44-ФЗ registration number.

    Only plain digit strings of length 6..20 are accepted — this is the
    conservative shape of real ЕИС registration numbers.  Anything else
    (non-digits, separators, query-style metacharacters such as
    '&', '#', '/', '?') is rejected.
    """
    if not isinstance(reg_number, str) or not reg_number:
        raise EisTransportError("reg_number must be a non-empty string")
    if not _REG_NUMBER_RE.fullmatch(reg_number):
        raise EisTransportError(
            f"Invalid registration number: {reg_number!r}. "
            "Expected 6-20 ASCII digits.",
        )


def validate_notice_type(notice_type: str) -> None:
    """Validate that a notice type is in the supported 44-ФЗ allow-list."""
    if notice_type not in _NOTICE_TYPES_44FZ:
        raise EisTransportError(
            f"Unsupported notice type: {notice_type!r}. "
            f"Allowed: {', '.join(_NOTICE_TYPES_44FZ)}.",
        )


async def fetch_page(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    user_agent: str = DEFAULT_USER_AGENT,
) -> str:
    """Fetch a single ЕИС page. Returns HTML as a string.

    Only https://zakupki.gov.ru URLs are accepted.  Redirects are not
    followed automatically; if the server issues a redirect, an
    EisTransportError is raised (fail-closed).

    Raises EisTransportError on any failure (HTTP error, timeout,
    DNS resolution, SSL issues, disallowed origin).
    """
    validate_eis_origin(url)

    headers = {
        "User-Agent": user_agent,
        "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    try:
        async with httpx.AsyncClient(verify=True) as client:
            response = await client.get(
                url,
                headers=headers,
                timeout=timeout,
                follow_redirects=False,
            )
    except httpx.TimeoutException as exc:
        raise EisTransportError(
            f"Timeout fetching {url}: {exc}",
        ) from exc
    except httpx.RequestError as exc:
        raise EisTransportError(
            f"Request error fetching {url}: {exc}",
        ) from exc

    if response.status_code in (301, 302, 303, 307, 308):
        raise EisTransportError(
            f"Redirect not allowed for {url} "
            f"(status {response.status_code}); cross-origin redirects are disabled.",
            status_code=response.status_code,
        )

    if response.status_code >= 400:
        raise EisTransportError(
            f"HTTP {response.status_code} for {url}",
            status_code=response.status_code,
        )

    return response.text


async def fetch_notice_by_reg_number(
    reg_number: str,
    *,
    notice_types: list[str] | None = None,
    **kwargs: object,
) -> tuple[str, str]:
    """Try fetching a notice page trying several ЕИС notice type codes.

    Returns (html, final_url).  Raises EisTransportError if all
    attempts fail.
    """
    validate_reg_number(reg_number)
    types_to_try = notice_types or list(_NOTICE_TYPES_44FZ)

    if notice_types is not None:
        for notice_type in types_to_try:
            validate_notice_type(notice_type)

    last_error: EisTransportError | None = None

    for notice_type in types_to_try:
        url = build_notice_url(reg_number, notice_type=notice_type)
        try:
            html = await fetch_page(url, **kwargs)  # type: ignore[arg-type]
            return html, url
        except EisTransportError as exc:
            last_error = exc
            continue

    raise EisTransportError(
        f"Could not fetch notice {reg_number} "
        f"with any notice type.  Last error: {last_error}",
    ) from last_error
