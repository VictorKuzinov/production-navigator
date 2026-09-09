"""HTML parser for ЕИС public notice pages (44-ФЗ).

Strategy: find field labels by their text content, then extract the
nearest associated value.  This avoids coupling to volatile CSS class
names or div positions.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup, NavigableString, Tag

from app.sources.eis_public.dto import ParsedEisNotice, ParsedEisPosition

# Renamed for clarity.
_REG_NUMBER_RE = re.compile(r"^\d{6,20}$")

# ---------------------------------------------------------------------------
# Label → field matching patterns
# ---------------------------------------------------------------------------
# Each tuple: (compiled regex matching the label text, field key)
_LABEL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"регистрационн\w*\s+номер", re.I),
        "reg_number",
    ),
    (
        re.compile(r"способ\s+определения\s+поставщик", re.I),
        "procurement_method",
    ),
    (
        re.compile(r"статус", re.I),
        "status",
    ),
    (
        re.compile(r"наименовани\w+\s+(объект\w*\s+)?закупк", re.I),
        "title",
    ),
    (
        re.compile(r"заказчик", re.I),
        "customer",
    ),
    (
        re.compile(r"электронн\w*\s+(?:торговая\s+)?площадк\w*\.?$", re.I),
        "platform",
    ),
    (
        re.compile(r"(^|\s)регион(\s|$)", re.I),
        "region",
    ),
    (
        re.compile(
            r"дата\s+и\s+время\s+окончания\s+срока\s+подачи\s+заявок",
            re.I,
        ),
        "application_deadline",
    ),
    (
        re.compile(
            r"дата\s+и\s+время\s+начала\s+срока\s+подачи\s+заявок",
            re.I,
        ),
        "application_start",
    ),
    (
        re.compile(r"результат\w*\s+закупк", re.I),
        "results_date",
    ),
    (
        re.compile(
            r"(?:начальн\w*\s*\(\s*максимальн\w*\s*\)\s*цен\w+\s+контракт"
            r"|максимально\w*\s+значени\w+\s+цен\w+\s+контракт)",
            re.I,
        ),
        "max_price",
    ),
    (
        re.compile(r"валют\w+\s+контракт", re.I),
        "currency",
    ),
    (
        re.compile(
            r"(срок\w*\s+выполнени\w+\s+(?:работ|услуг|контракт))",
            re.I,
        ),
        "execution_deadline",
    ),
    (
        re.compile(r"место\s+(выполнени\w+\s+работ|оказания\s+услуг|поставк)", re.I),
        "delivery_location",
    ),
    (
        re.compile(r"гаранти\w+", re.I),
        "warranty",
    ),
]

_OKPD2_RE = re.compile(r"\d{2}\.\d{2}\.\d{2}\.\d{3}")

_LABEL_CONTAINER_TAGS = frozenset(
    {
        "html",
        "head",
        "body",
        "div",
        "section",
        "table",
        "thead",
        "tbody",
        "tfoot",
        "tr",
        "ul",
        "ol",
        "form",
        "fieldset",
    }
)

# Conservative detection of a purchase positions table: requires a set of
# columns characteristic of positions, i.e. a name-like column plus at
# least one structural column (OKPD2/code), and (optionally) unit /
# quantity / price.  A single word like "наименование" alone is not
# enough.
_POSITIONS_HEADER_REQS = {
    "name": re.compile(r"наименован", re.I),
    "okpd2": re.compile(r"окпд|код\s+позици", re.I),
    "unit": re.compile(r"единиц|ед\.изм|ед\. изм", re.I),
    "quantity": re.compile(r"количеств|кол-во", re.I),
    "price": re.compile(r"цен\w+\s+за\s+ед|стоимост", re.I),
}

_PRICE_RE = re.compile(
    r"([\d\s,.]+)\s*(₽|руб|RUB|EUR|USD|€|\$)?",
    re.I,
)

_Russian_MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _text(tag: Tag | NavigableString | None) -> str:
    """Return stripped visible text of a tag."""
    if tag is None:
        return ""
    return tag.get_text(separator=" ", strip=True)


def _extract_value_after(label_tag: Tag) -> str:
    """Given a label element, find the most likely value element nearby.

    Heuristics (tried in order):
    1. Next sibling element in the same parent.
    2. Parent's next sibling element.
    3. Text following the label within the same parent cell.

    IMPORTANT: in every branch the candidate text is examined and, if it
    does not look like a value (e.g. it is actually the next sibling
    *label*), it is rejected.  In particular, when the descendant of an
    adjacent label is a known label, an empty/missing current value must
    NOT be replaced by the text of the neighbouring field.
    """
    # 1. Next sibling element
    next_sib = label_tag.find_next_sibling()
    if next_sib and isinstance(next_sib, Tag):
        if _looks_like_label(_text(next_sib)):
            return ""
        text = _text(next_sib)
        if text:
            return text

    # 2. Parent's next sibling
    parent = label_tag.parent
    if parent and isinstance(parent, Tag):
        parent_next = parent.find_next_sibling()
        if parent_next and isinstance(parent_next, Tag):
            if _looks_like_label(_text(parent_next)):
                return ""
            text = _text(parent_next)
            if text:
                return text

    # 3. Remaining text in same container
    parent_text = _text(parent) if parent else ""
    label_text = _text(label_tag)
    if parent_text and label_text and len(parent_text) > len(label_text):
        remainder = parent_text.split(label_text, 1)[-1].strip("-:— \t")
        if remainder and _looks_like_label(remainder):
            return ""
        return remainder

    return ""


def _looks_like_label(text: str) -> bool:
    """Является ли ``text`` осмысленным ярлыком известного поля.

    Используется, чтобы предотвратить подстановку пустого значения
    текущего поля текстом (ярлыком) соседнего поля.

    Текст считается ярлыком, только если один из известных шаблонов
    совпадает с начала строки (``match``), а не встречается где-то
    внутри свободного текста значения.  Это отсекает ложные
    срабатывания, когда слово-шаблон (например «заказчик» или
    «площадка») просто присутствует внутри реального значения —
    такое значение нельзя принимать за соседний ярлык.
    """
    stripped = text.strip().strip(":—\t ")
    if not stripped:
        return False
    for pattern, _key in _LABEL_PATTERNS:
        if pattern.match(stripped) and len(stripped) <= 160:
            return True
    return False


def _parse_price(text: str) -> tuple[Decimal | None, str | None]:
    """Extract (amount, currency) from a price text string."""
    cleaned = text.replace("\xa0", "").replace(" ", "").replace(",", ".")
    amount: Decimal | None = None
    currency: str | None = None

    m = _PRICE_RE.search(cleaned)
    if m:
        num_str = m.group(1).replace(" ", "")
        try:
            amount = Decimal(num_str)
        except InvalidOperation:
            pass
        symbol = m.group(2)
        if symbol:
            symbol_upper = symbol.upper()
            if symbol_upper in ("RUB", "РУБ", "₽"):
                currency = "RUB"
            elif symbol_upper in ("EUR", "€"):
                currency = "EUR"
            elif symbol_upper in ("USD", "$"):
                currency = "USD"

    if amount is None:
        # Fallback: try the whole cleaned string
        try:
            amount = Decimal(cleaned)
        except InvalidOperation:
            pass

    if amount is not None and currency is None:
        currency = "RUB"

    return amount, currency


def _parse_russian_date(text: str) -> date | None:
    """Parse 'DD month_name YYYY' format."""
    m = re.search(
        r"(\d{1,2})\s+" + "(" + "|".join(_Russian_MONTHS) + r")\s+" + r"(\d{4})",
        text,
        re.I,
    )
    if not m:
        return None
    day = int(m.group(1))
    month = _Russian_MONTHS[m.group(2).lower()]
    year = int(m.group(3))
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _parse_datetime(text: str) -> datetime | None:
    """Parse 'DD.MM.YYYY HH:MM' or 'DD month_name YYYY HH:MM'."""
    # Try DD.MM.YYYY HH:MM first
    m = re.search(
        r"(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2})",
        text,
    )
    if m:
        try:
            return datetime(
                int(m.group(3)),
                int(m.group(2)),
                int(m.group(1)),
                int(m.group(4)),
                int(m.group(5)),
            )
        except ValueError:
            pass

    # Try DD month_name YYYY
    d = _parse_russian_date(text)
    if d:
        return datetime(d.year, d.month, d.day)

    return None


def _parse_okpd2_from_text(text: str) -> list[str]:
    """Extract OKPD2 codes from arbitrary text."""
    codes: list[str] = []
    for m in _OKPD2_RE.finditer(text):
        code = m.group(0)
        if code not in codes:
            codes.append(code)
    return codes


def _parse_money_value(text: str) -> Decimal | None:
    """Parse a monetary value, stripping currency symbols and spaces."""
    cleaned = text.replace("\xa0", "").replace(" ", "")
    cleaned = re.sub(r"[₽рубRUBEURUSD€$]+", "", cleaned, flags=re.I)
    cleaned = cleaned.replace(",", ".").strip()
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


# ---------------------------------------------------------------------------
# Positions table parsing
# ---------------------------------------------------------------------------


def _looks_like_positions_header(header_text: str) -> bool:
    """Return True if the header suggests a purchase positions table.

    Requires a name column and at least one structural column
    (OKPD2/code, unit, quantity, price).  A table containing just the
    word "наименование" (e.g. the generic information table's "Наименование
    объекта закупки") is NOT treated as a positions table.
    """
    lower = header_text.lower()
    has_name = bool(_POSITIONS_HEADER_REQS["name"].search(lower))
    structural = [
        _POSITIONS_HEADER_REQS["okpd2"].search(lower),
        _POSITIONS_HEADER_REQS["unit"].search(lower),
        _POSITIONS_HEADER_REQS["quantity"].search(lower),
        _POSITIONS_HEADER_REQS["price"].search(lower),
    ]
    has_structural = any(structural)
    return has_name and has_structural


def _find_positions_table(soup: BeautifulSoup) -> Tag | None:
    """Locate the purchase positions table.

    Searches *all* tables, skipping those that do not look like a
    positions table (conservative column set).  If the first matching
    table is a generic info table, parsing continues to later tables.
    """
    for table in soup.find_all("table"):
        header_text = _text(table.find("thead")) if table.find("thead") else ""
        if not header_text:
            first_row = table.find("tr")
            header_text = _text(first_row) if first_row else ""
        if _looks_like_positions_header(header_text):
            return table
    return None


def _parse_positions_table(table: Tag) -> list[ParsedEisPosition]:
    """Parse purchase positions from an HTML table."""
    positions: list[ParsedEisPosition] = []

    # Determine column indices from header
    header_row = table.find("thead")
    if not header_row:
        header_row = table.find("tr")
    if not header_row:
        return positions

    headers = [_text(th) for th in header_row.find_all(["th", "td"])]
    col_map = _map_columns(headers)

    tbody = table.find("tbody")
    rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]

    def _cell(idx: int | None) -> str:
        """Return the text of a mapped column, or "" if out of bounds."""
        if idx is None or not (0 <= idx < len(cells)):
            return ""
        return cells[idx]

    for row in rows:
        cells = [_text(td) for td in row.find_all(["td", "th"])]
        if len(cells) < 2:
            continue

        # Skip merged/colspan rows (real ЕИС renders characteristic
        # blocks inside the product table as colspan cells).
        has_colspan = any(
            str(td.get("colspan") or "").isdigit() for td in row.find_all(["td", "th"])
        )
        if has_colspan:
            continue

        # Skip characteristic sub-rows: they have fewer physical cells
        # than the header column count.
        if len(cells) < len(headers):
            continue

        # At this point the row resembles a product row.  Access the
        # mapped columns defensively (a malformed row must not crash the
        # parser).
        name = _cell(col_map.get("name"))
        if not name:
            continue
        if "характеристик" in name.lower() or "инструкция" in name.lower():
            continue

        okpd2 = None
        okpd2_text = _cell(col_map.get("okpd2"))
        if okpd2_text:
            codes = _parse_okpd2_from_text(okpd2_text)
            okpd2 = codes[0] if codes else None

        unit = _cell(col_map.get("unit")) or None

        quantity_text = _cell(col_map.get("quantity"))
        quantity = _parse_money_value(quantity_text) if quantity_text else None

        price_text = _cell(col_map.get("price"))
        price = _parse_money_value(price_text) if price_text else None

        positions.append(
            ParsedEisPosition(
                okpd2_code=okpd2,
                name=name,
                unit=unit,
                unit_price=price,
                quantity=quantity,
            )
        )

    return positions


def _map_columns(headers: Sequence[str]) -> dict[str, int]:
    """Map logical column names to their indices."""
    mapping: dict[str, int] = {}
    for idx, h in enumerate(headers):
        h_lower = h.lower()
        if "номер" in h_lower or h_lower.strip() in ("№", "n", "п/п"):
            continue
        if "окпд" in h_lower or "код позици" in h_lower:
            mapping["okpd2"] = idx
        elif "наименован" in h_lower:
            mapping["name"] = idx
        elif "единиц" in h_lower or "ед.изм" in h_lower or "ед. изм" in h_lower:
            mapping["unit"] = idx
        elif "количеств" in h_lower or "кол-во" in h_lower:
            mapping["quantity"] = idx
        elif ("цен" in h_lower and "единиц" in h_lower) or (
            "цен" in h_lower and "ед." in h_lower
        ):
            mapping["price"] = idx
        elif "стоимость" in h_lower:
            if "price" not in mapping:
                mapping["price_total"] = idx
    return mapping


# ---------------------------------------------------------------------------
# Real ЕИС structure helpers (section__title / section__info)
# ---------------------------------------------------------------------------

_EIS_SECTION_TITLE_CLASSES = ("section__title", "blockInfo__title")
_EIS_SECTION_INFO_CLASSES = ("section__info", "blockInfo__content")

# In section markup the label is a dedicated span, so the platform
# pattern does not need the "end of label only" anchor that protects the
# generic th/td path from picking up a value cell.
_SECTION_PLATFORM_PATTERN = re.compile(
    r"электронн\w*\s+(?:торговая\s+)?площадк\w*",
    re.I,
)


def _match_section_label_text(text: str) -> str | None:
    """Return the field key for a section label text (real ЕИС layout)."""
    for pattern, key in _LABEL_PATTERNS:
        if pattern.search(text):
            return key
    if _SECTION_PLATFORM_PATTERN.search(text):
        return "platform"
    return None


def _extract_from_sections(
    soup: BeautifulSoup,
    extracted: dict[str, str],
) -> None:
    """Extract label→value pairs from real ЕИС section markup.

    Real ЕИС notice pages render each field as::

        <section class="blockInfo__section section">
            <span class="section__title">label</span>
            <span class="section__info">value</span>
        </section>

    This is the dominant structural pattern and the selectors are
    isolated here (not spread across the parser) and covered by
    fixture tests.

    IMPORTANT: a section with an empty value must not "borrow" the text
    of the following section's title.  If the value span is missing or
    empty, no value is recorded for the current field.  If the value
    span's text actually looks like a neighbouring field label, it is
    also rejected.
    """
    for section in soup.find_all("section", class_="blockInfo__section"):
        title_span = section.find("span", class_=_EIS_SECTION_TITLE_CLASSES)
        if not title_span:
            title_span = section.find("h2", class_=_EIS_SECTION_TITLE_CLASSES)
        if not title_span:
            continue
        title_text = _text(title_span)
        if not title_text:
            continue

        field_key = _match_section_label_text(title_text)
        if field_key is None or field_key in extracted:
            continue

        info_span = section.find("span", class_=_EIS_SECTION_INFO_CLASSES)
        if not info_span:
            # Try any following element in the section
            info_span = section.find(["span", "div"], class_=_EIS_SECTION_INFO_CLASSES)
        if info_span is None:
            continue
        value = _text(info_span).strip()
        # If the value cell actually holds a neighbouring label, do not
        # consume it (it will be parsed when its own section is reached).
        if not value or _looks_like_label(value):
            continue
        extracted[field_key] = value


def _extract_reg_number_from_breadcrumb(soup: BeautifulSoup) -> str | None:
    """Extract the registration number from a breadcrumb span.

    Real ЕИС shows it as ``<span class="navBreadcrumb__text">№ 0148...</span>``.
    """
    for span in soup.find_all("span"):
        classes = [c.lower() for c in (span.get("class") or [])]
        if any("breadcrumb" in c for c in classes) and any(
            "text" in c for c in classes
        ):
            text = _text(span)
            m = re.search(r"№\s*([0-9]{6,})", text)
            if m:
                candidate = m.group(1)
                if _REG_NUMBER_RE.fullmatch(candidate):
                    return candidate
    return None


def _match_label_text(text: str) -> str | None:
    """Return the field key for a label text, or None if it matches none."""
    for pattern, key in _LABEL_PATTERNS:
        if pattern.search(text):
            return key
    return None


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------


class EisParseError(Exception):
    """Raised when HTML cannot be parsed as a valid ЕИС notice."""


def parse_notice_html(
    html: str,
    *,
    source_url: str | None = None,
) -> ParsedEisNotice:
    """Parse a ЕИС public notice HTML page into a ParsedEisNotice DTO.

    Raises EisParseError if the HTML does not resemble a ЕИС notice page.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Collect all field label → value pairs
    extracted: dict[str, str] = {}
    for label_tag in soup.find_all(_match_label):
        field_key = label_tag.get("_field_key", "")
        if field_key and field_key not in extracted:
            value = _extract_value_after(label_tag)
            if value:
                extracted[field_key] = value

    # Real ЕИС structure: <section class="blockInfo__section">
    #   <span class="section__title">label</span>
    #   <span class="section__info">value</span>
    # </section>
    _extract_from_sections(soup, extracted)

    # Fallback: search in table rows (th/td layout)
    for row in soup.find_all("tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) >= 2:
            for i in range(len(cells) - 1):
                cell_text = _text(cells[i])
                for pattern, key in _LABEL_PATTERNS:
                    if pattern.search(cell_text) and key not in extracted:
                        value = _text(cells[i + 1])
                        # Guard against borrowing a neighbouring label as
                        # this field's value.
                        if value and not _looks_like_label(value):
                            extracted[key] = value
                        break

    procurement_number = extracted.get("reg_number", "").strip()
    if not procurement_number:
        # Fallback: registration number in a breadcrumb
        # <span class="navBreadcrumb__text">№ 0148200005224000001</span>
        proc_number = _extract_reg_number_from_breadcrumb(soup)
        if proc_number:
            procurement_number = proc_number
        else:
            raise EisParseError(
                "Could not find registration number in the ЕИС page.",
            )

    # Registry number must be a plain digit string of the expected shape.
    if not _REG_NUMBER_RE.fullmatch(procurement_number):
        raise EisParseError(
            f"Invalid registration number in ЕИС page: {procurement_number!r}.",
        )

    title = extracted.get("title", "").strip()
    if not title:
        raise EisParseError(
            "Could not find notice title in the ЕИС page.",
        )

    # Parse price
    price_text = extracted.get("max_price", "")
    max_price, currency = _parse_price(price_text)
    if currency is None:
        currency_text = extracted.get("currency", "")
        if "евро" in currency_text.lower() or "eur" in currency_text.lower():
            currency = "EUR"
        elif "доллар" in currency_text.lower() or "usd" in currency_text.lower():
            currency = "USD"
        elif max_price is not None:
            currency = "RUB"

    # Parse dates
    application_deadline = _parse_datetime(extracted.get("application_deadline", ""))
    application_start = _parse_datetime(extracted.get("application_start", ""))
    results_date = _parse_datetime(extracted.get("results_date", ""))

    # OKPD2 from the page (beyond positions)
    okpd2_codes: list[str] = []
    okpd2_text = extracted.get("okpd2", "")
    if okpd2_text:
        okpd2_codes.extend(_parse_okpd2_from_text(okpd2_text))

    # Positions table
    positions_table = _find_positions_table(soup)
    positions: list[ParsedEisPosition] = []
    if positions_table:
        positions = _parse_positions_table(positions_table)

    # Collect OKPD2 from positions
    for pos in positions:
        if pos.okpd2_code and pos.okpd2_code not in okpd2_codes:
            okpd2_codes.append(pos.okpd2_code)

    return ParsedEisNotice(
        procurement_number=procurement_number,
        title=title,
        law="44-ФЗ",
        procurement_method=extracted.get("procurement_method") or None,
        status_text=extracted.get("status") or None,
        customer=extracted.get("customer") or None,
        platform_name=extracted.get("platform") or None,
        platform_url=None,
        region=extracted.get("region") or None,
        application_start=application_start,
        application_deadline=application_deadline,
        results_date=results_date,
        max_price=max_price,
        currency=currency,
        execution_deadline_text=extracted.get("execution_deadline") or None,
        delivery_location=extracted.get("delivery_location") or None,
        okpd2_codes=okpd2_codes,
        positions=positions,
        quality_warranty=extracted.get("warranty") or None,
        source_url=source_url,
    )


def _match_label(tag: Tag) -> bool:
    """BeautifulSoup filter: returns True if tag text matches a known label.

    Only leaf-ish elements are considered — i.e. short fragments that
    look like a single field label.  Large container elements (html,
    body, div, table, tr, etc.) are rejected so their aggregated text
    is not mistaken for a label.
    """
    if not isinstance(tag, Tag):
        return False
    if tag.name in _LABEL_CONTAINER_TAGS:
        return False

    text = _text(tag)
    if not text:
        return False
    # A label should be a short fragment, not a container of many values.
    if len(text) > 160:
        return False

    for pattern, key in _LABEL_PATTERNS:
        if pattern.search(text):
            tag["_field_key"] = key  # type: ignore[attr-defined]
            return True
    return False
