"""EIS Public Source Adapter — 44-ФЗ public notice fetcher.

Usage::

    from app.sources.eis_public import fetch_and_parse_notice

    notice = await fetch_and_parse_notice(
        url="https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0373200049624000001",
    )

    # or by registration number:
    notice = await fetch_and_parse_notice(reg_number="0373200049624000001")
"""

from __future__ import annotations

from app.sources.eis_public.dto import ParsedEisNotice, ParsedEisPosition
from app.sources.eis_public.parser import EisParseError, parse_notice_html
from app.sources.eis_public.projector import (
    EisProjectionError,
    project_to_prepared_input,
)
from app.sources.eis_public.transport import (
    EisTransportError,
    build_notice_url,
    fetch_notice_by_reg_number,
    fetch_page,
)

__all__ = [
    "EisParseError",
    "EisProjectionError",
    "EisTransportError",
    "ParsedEisNotice",
    "ParsedEisPosition",
    "build_notice_url",
    "fetch_and_parse_notice",
    "fetch_notice_by_reg_number",
    "fetch_page",
    "parse_notice_html",
    "project_to_prepared_input",
]


async def fetch_and_parse_notice(
    *,
    url: str | None = None,
    reg_number: str | None = None,
) -> ParsedEisNotice:
    """High-level convenience: fetch + parse in one call.

    Either ``url`` or ``reg_number`` must be provided.
    Raises EisTransportError on network failures,
    EisParseError on unparseable HTML.
    """
    if url is None and reg_number is None:
        raise ValueError("Provide either url or reg_number.")

    if url is not None:
        html = await fetch_page(url)
        return parse_notice_html(html, source_url=url)

    html, final_url = await fetch_notice_by_reg_number(reg_number)  # type: ignore[arg-type]
    return parse_notice_html(html, source_url=final_url)
