"""Tests for ЕИС HTTP transport (mocked) — includes remediation
(security hardening)."""

from __future__ import annotations

import httpx
import pytest

from app.sources.eis_public.transport import (
    EisTransportError,
    build_notice_url,
    fetch_notice_by_reg_number,
    fetch_page,
    validate_notice_type,
    validate_reg_number,
)


class _FakeClient:
    """Minimal httpx.AsyncClient stand-in with a configurable `get`."""

    def __init__(
        self,
        get_impl=None,
        *,
        verify: object = True,
    ) -> None:
        self._get_impl = get_impl or (lambda **_: httpx.Response(200, text=""))
        self.verify = verify

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def get(self, url: str, **kwargs: object) -> httpx.Response:
        result = self._get_impl(url=url, **kwargs)
        return result


def _patch_client(
    monkeypatch: pytest.MonkeyPatch,
    get_impl,
    *,
    verify: object = True,
    capture: list | None = None,
) -> None:
    """Patch httpx.AsyncClient.

    The fake records the ``verify`` kwarg (if ``capture`` provided) so
    tests can assert that production transport enables TLS verification.
    """

    def _factory(**kwargs: object) -> _FakeClient:
        if capture is not None:
            capture.append(kwargs)
        return _FakeClient(get_impl=get_impl, verify=kwargs.get("verify", True))

    monkeypatch.setattr(
        "app.sources.eis_public.transport.httpx.AsyncClient",
        _factory,
    )


# -----------------------------------------------------------------------
# URL building & validation
# -----------------------------------------------------------------------


class TestBuildNoticeUrl:
    def test_default_type(self) -> None:
        url = build_notice_url("0373200049624000001")
        assert "regNumber=0373200049624000001" in url
        assert "/ea20/" in url
        assert url.startswith("https://zakupki.gov.ru")

    def test_valid_reg_number_short(self) -> None:
        assert build_notice_url("123456", notice_type="ok1").startswith(
            "https://zakupki.gov.ru"
        )

    def test_invalid_reg_number_letters(self) -> None:
        with pytest.raises(EisTransportError, match="registration number"):
            build_notice_url("12F1200")

    def test_invalid_reg_number_short(self) -> None:
        with pytest.raises(EisTransportError, match="registration number"):
            build_notice_url("123")

    def test_invalid_reg_number_with_query_chars(self) -> None:
        with pytest.raises(EisTransportError, match="registration number"):
            build_notice_url("123456&evil=1")

    def test_invalid_reg_number_with_slash(self) -> None:
        with pytest.raises(EisTransportError, match="registration number"):
            build_notice_url("123456/7")

    def test_invalid_reg_number_with_question(self) -> None:
        with pytest.raises(EisTransportError, match="registration number"):
            build_notice_url("123456?x=1")

    def test_invalid_notice_type(self) -> None:
        with pytest.raises(EisTransportError, match="notice type"):
            build_notice_url("123456", notice_type="<script>")

    def test_validate_reg_number_allows_digits_only(self) -> None:
        validate_reg_number("0373200049624000001")
        with pytest.raises(EisTransportError):
            validate_reg_number("03732 00049")

    def test_validate_notice_type_allow_list(self) -> None:
        validate_notice_type("ea20")
        with pytest.raises(EisTransportError):
            validate_notice_type("custom")


# -----------------------------------------------------------------------
# fetch_page
# -----------------------------------------------------------------------


class TestFetchPage:
    @pytest.mark.asyncio
    async def test_follow_redirects_is_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Transport must not follow redirects automatically: every request
        to client.get carries follow_redirects=False (fail-closed)."""
        request_kwargs: list[dict] = []

        def get_impl(url: str, **kwargs: object) -> httpx.Response:
            request_kwargs.append(kwargs)
            return httpx.Response(200, text="<html>OK</html>")

        _patch_client(monkeypatch, get_impl)
        url = (
            "https://zakupki.gov.ru/epz/order/notice/ea20/"
            "view/common-info.html?regNumber=0373200049624000001"
        )
        html = await fetch_page(url)
        assert request_kwargs, "fetch_page never called client.get"
        assert request_kwargs[0].get("follow_redirects") is False
        assert html == "<html>OK</html>"

    @pytest.mark.asyncio
    async def test_verify_true_by_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Production transport must NOT disable TLS verification."""
        captured: list[dict] = []
        _patch_client(
            monkeypatch,
            lambda **_: httpx.Response(200, text="<html>OK</html>"),
            capture=captured,
        )
        await fetch_page("https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0373200049624000001")
        assert captured, "AsyncClient factory was never called"
        assert captured[0].get("verify") is not False
        assert captured[0].get("verify") is True or captured[0].get("verify") is None

    @pytest.mark.asyncio
    async def test_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        url = (
            "https://zakupki.gov.ru/epz/order/notice/ea20/"
            "view/common-info.html?regNumber=0373200049624000001"
        )

        def get_impl(**kwargs: object) -> httpx.Response:
            assert kwargs.get("follow_redirects") is False
            return httpx.Response(200, text="<html>OK</html>")

        _patch_client(monkeypatch, get_impl)
        html = await fetch_page(url)
        assert html == "<html>OK</html>"

    @pytest.mark.asyncio
    async def test_http_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def get_impl(**kwargs: object) -> httpx.Response:
            return httpx.Response(403, text="Forbidden")

        url = (
            "https://zakupki.gov.ru/epz/order/notice/ea20/"
            "view/common-info.html?regNumber=0373200049624000001"
        )
        _patch_client(monkeypatch, get_impl)
        with pytest.raises(EisTransportError, match="403"):
            await fetch_page(url)

    @pytest.mark.asyncio
    async def test_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def get_impl(**kwargs: object) -> httpx.Response:
            raise httpx.TimeoutException("timeout")

        url = (
            "https://zakupki.gov.ru/epz/order/notice/ea20/"
            "view/common-info.html?regNumber=0373200049624000001"
        )
        _patch_client(monkeypatch, get_impl)
        with pytest.raises(EisTransportError, match="Timeout"):
            await fetch_page(url)

    @pytest.mark.asyncio
    async def test_redirect_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A redirect (3xx) must be surfaced as an error, not followed."""
        def get_impl(**kwargs: object) -> httpx.Response:
            assert kwargs.get("follow_redirects") is False
            return httpx.Response(302, headers={"Location": "https://evil.example/"},
                                  text="")

        _patch_client(monkeypatch, get_impl)
        url = (
            "https://zakupki.gov.ru/epz/order/notice/ea20/"
            "view/common-info.html?regNumber=0373200049624000001"
        )
        with pytest.raises(EisTransportError, match="Redirect"):
            await fetch_page(url)

    # ---- Origin / scheme / host hardening ------------------------------

    @pytest.mark.asyncio
    async def test_http_url_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_client(monkeypatch, lambda **_: httpx.Response(200, text=""))
        with pytest.raises(EisTransportError, match="https"):
            await fetch_page(
                "http://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html"
            )

    @pytest.mark.asyncio
    async def test_loopback_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_client(monkeypatch, lambda **_: httpx.Response(200, text=""))
        with pytest.raises(EisTransportError, match="host"):
            await fetch_page("https://127.0.0.1/notice")

    @pytest.mark.asyncio
    async def test_ipv6_loopback_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_client(monkeypatch, lambda **_: httpx.Response(200, text=""))
        with pytest.raises(EisTransportError, match="host"):
            await fetch_page("https://[::1]/notice")

    @pytest.mark.asyncio
    async def test_other_host_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_client(monkeypatch, lambda **_: httpx.Response(200, text=""))
        with pytest.raises(EisTransportError, match="host"):
            await fetch_page("https://example.com/notice")

    @pytest.mark.asyncio
    async def test_userinfo_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_client(monkeypatch, lambda **_: httpx.Response(200, text=""))
        with pytest.raises(EisTransportError, match="userinfo|host|Userinfo"):
            await fetch_page("https://user:pass@zakupki.gov.ru/notice")

    @pytest.mark.asyncio
    async def test_localhost_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_client(monkeypatch, lambda **_: httpx.Response(200, text=""))
        with pytest.raises(EisTransportError, match="host"):
            await fetch_page("https://localhost/notice")

    @pytest.mark.asyncio
    async def test_malformed_url_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_client(monkeypatch, lambda **_: httpx.Response(200, text=""))
        with pytest.raises(EisTransportError):
            await fetch_page("not-a-url")


# -----------------------------------------------------------------------
# fetch_notice_by_reg_number
# -----------------------------------------------------------------------


class TestFetchNoticeByRegNumber:
    @pytest.mark.asyncio
    async def test_valid_reg_number_succeeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def get_impl(**kwargs: object) -> httpx.Response:
            return httpx.Response(200, text="<html>found</html>")

        _patch_client(monkeypatch, get_impl)
        html, url = await fetch_notice_by_reg_number("0373200049624000001")
        assert html == "<html>found</html>"
        assert "regNumber=0373200049624000001" in url

    @pytest.mark.asyncio
    async def test_invalid_reg_number_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_client(monkeypatch, lambda **_: httpx.Response(200, text=""))
        with pytest.raises(EisTransportError, match="registration number"):
            await fetch_notice_by_reg_number("no-display")

    @pytest.mark.asyncio
    async def test_unknown_notice_type_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_client(monkeypatch, lambda **_: httpx.Response(200, text=""))
        with pytest.raises(EisTransportError, match="notice type"):
            await fetch_notice_by_reg_number(
                "0373200049624000001",
                notice_types=["custom"],
            )

    @pytest.mark.asyncio
    async def test_all_fail_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def get_impl(**kwargs: object) -> httpx.Response:
            return httpx.Response(404, text="Not Found")

        _patch_client(monkeypatch, get_impl)
        with pytest.raises(EisTransportError, match="Could not fetch"):
            await fetch_notice_by_reg_number(
                "999999999999",
                notice_types=["ea20"],
            )
