"""Tests for ЕИС HTML parser — includes remediation tests for
label/value boundary isolation and positions-table detection."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.sources.eis_public.dto import ParsedEisNotice
from app.sources.eis_public.parser import (
    EisParseError,
    _parse_okpd2_from_text,
    _parse_price,
    _parse_russian_date,
    parse_notice_html,
)

# -----------------------------------------------------------------------
# Helper: minimal valid HTML that produces a parseable notice
# -----------------------------------------------------------------------


def _make_html(
    *,
    reg_number: str = "0373200049624000001",
    title: str = "Тестовая закупка",
    extra_rows: str = "",
) -> str:
    return f"""
    <html><body>
    <table>
        <tr><th>Регистрационный номер</th><td>{reg_number}</td></tr>
        <tr><th>Наименование объекта закупки</th><td>{title}</td></tr>
        {extra_rows}
    </table>
    </body></html>
    """


def _make_sections_html(rows: str) -> str:
    return f"""
    <html><body>
    <div><span class="navBreadcrumb__text">№ 0373200049624000001</span></div>
    {rows}
    </body></html>
    """


# -----------------------------------------------------------------------
# OKPD2 regex extraction
# -----------------------------------------------------------------------


class TestOkpd2Regex:
    def test_single_code(self) -> None:
        assert _parse_okpd2_from_text("25.62.10.000") == ["25.62.10.000"]

    def test_code_in_text(self) -> None:
        text = "Код: 25.62.10.000 — Металлообработка"
        assert _parse_okpd2_from_text(text) == ["25.62.10.000"]

    def test_multiple_codes(self) -> None:
        text = "25.62.10.000 и 25.62.20.000"
        assert _parse_okpd2_from_text(text) == [
            "25.62.10.000",
            "25.62.20.000",
        ]

    def test_no_codes(self) -> None:
        assert _parse_okpd2_from_text("никаких кодов") == []

    def test_deduplication(self) -> None:
        text = "25.62.10.000 и снова 25.62.10.000"
        assert _parse_okpd2_from_text(text) == ["25.62.10.000"]


# -----------------------------------------------------------------------
# Price parsing
# -----------------------------------------------------------------------


class TestPriceParsing:
    def test_basic_price(self) -> None:
        amount, currency = _parse_price("1 000 000,00 ₽")
        assert amount == Decimal("1000000.00")
        assert currency == "RUB"

    def test_price_no_symbol(self) -> None:
        amount, currency = _parse_price("500 000.00")
        assert amount == Decimal("500000.00")
        assert currency == "RUB"

    def test_price_with_rub_text(self) -> None:
        amount, currency = _parse_price("1 000 000,00 руб")
        assert amount == Decimal("1000000.00")
        assert currency == "RUB"

    def test_price_eur(self) -> None:
        amount, currency = _parse_price("10 000,00 EUR")
        assert amount == Decimal("10000.00")
        assert currency == "EUR"

    def test_price_with_nbsp(self) -> None:
        amount, currency = _parse_price("1\u00a0000\u00a0000,00 ₽")
        assert amount == Decimal("1000000.00")
        assert currency == "RUB"

    def test_empty_price(self) -> None:
        amount, currency = _parse_price("")
        assert amount is None
        assert currency is None


# -----------------------------------------------------------------------
# Russian date parsing
# -----------------------------------------------------------------------


class TestRussianDate:
    def test_january(self) -> None:
        result = _parse_russian_date("15 января 2024")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_december(self) -> None:
        result = _parse_russian_date("1 декабря 2023")
        assert result is not None
        assert result.month == 12

    def test_invalid(self) -> None:
        assert _parse_russian_date("не дата") is None


# -----------------------------------------------------------------------
# Real ЕИС structure (section__title / section__info + product table)
# -----------------------------------------------------------------------

_REAL_EIS_HTML = (
    "<html><body>"
    "<div>"
    '    <span class="navBreadcrumb__text">№ 0148200005224000001</span>'
    "</div>"
    '<section class="blockInfo__section section">'
    '    <h2 class="blockInfo__title">Общая информация</h2>'
    "</section>"
    '<section class="blockInfo__section section">'
    '    <span class="section__title">Способ определения поставщика'
    " (подрядчика, исполнителя)</span>"
    '    <span class="section__info">Электронный аукцион</span>'
    "</section>"
    '<section class="blockInfo__section section">'
    '    <span class="section__title">Наименование электронной площадки '
    "в информационно-телекоммуникационной сети «Интернет»</span>"
    '    <span class="section__info">РТС-тендер</span>'
    "</section>"
    '<section class="blockInfo__section section">'
    '    <span class="section__title">Наименование объекта закупки</span>'
    '    <span class="section__info">Поставка рамок со стеклом</span>'
    "</section>"
    '<section class="blockInfo__section section">'
    '    <span class="section__title">Заказчик</span>'
    '    <span class="section__info">МИНИСТЕРСТВО СТРОИТЕЛЬНОГО КОМПЛЕКСА '
    "МОСКОВСКОЙ ОБЛАСТИ</span>"
    "</section>"
    '<section class="blockInfo__section section">'
    '    <span class="section__title">Регион</span>'
    '    <span class="section__info">Московская обл</span>'
    "</section>"
    '<section class="blockInfo__section section">'
    '    <span class="section__title">Начальная (максимальная) цена '
    "контракта</span>"
    '    <span class="section__info">160 926,00</span>'
    "</section>"
    '<section class="blockInfo__section section">'
    '    <span class="section__title">Дата и время окончания срока '
    "подачи заявок</span>"
    '    <span class="section__info">26.02.2024 10:00 (МСК)</span>'
    "</section>"
    "<table>"
    "    <thead><tr>"
    "        <th></th><th>Код позиции</th>"
    "        <th>Наименование товара, работы, услуги</th>"
    "        <th>Ед. измерения</th>"
    "        <th>Количество (объем работы, услуги)</th>"
    "        <th>Цена за ед., ₽</th><th>Стоимость, ₽</th>"
    "    </tr></thead>"
    "    <tbody>"
    "        <tr>"
    "            <td></td><td>22.29.26.190</td>"
    "            <td>Рамка со стеклом А4 Формат А4 "
    "Тип размещения рамки Вертикальный</td>"
    "            <td>Штука</td><td>400,00</td><td>296,18</td>"
    "            <td>118 472,00</td>"
    "        </tr>"
    "        <tr>"
    '            <td></td><td colspan="6">Наименование характеристики '
    "Значение характеристики"
    "                Единица измерения характеристики "
    "Инструкция по заполнению характеристик в заявке"
    "                Формат А4 Значение характеристики не может быть "
    "пустым</td>"
    "        </tr>"
    "        <tr>"
    '            <td></td><td colspan="6">Наименование характеристики '
    "Значение характеристики"
    "                Единица измерения характеристики "
    "Инструкция по заполнению характеристик в заявке"
    "                Ширина фотографии ≥ 209 и ≤ 211 Миллиметр</td>"
    "        </tr>"
    "        <tr>"
    "            <td></td><td>22.29.26.190</td>"
    "            <td>Рамка со стеклом А3 Формат А3 "
    "Тип крепления подложки гибкие лепестки</td>"
    "            <td>Штука</td><td>100,00</td><td>424,54</td>"
    "            <td>42 454,00</td>"
    "        </tr>"
    "    </tbody>"
    "</table>"
    "</body></html>"
)


class TestRealEisSectionStructure:
    def test_section_structure_parsed(self) -> None:
        notice = parse_notice_html(_REAL_EIS_HTML)
        assert notice.procurement_number == "0148200005224000001"
        assert notice.title == "Поставка рамок со стеклом"
        assert notice.procurement_method == "Электронный аукцион"
        assert (
            notice.customer == "МИНИСТЕРСТВО СТРОИТЕЛЬНОГО КОМПЛЕКСА МОСКОВСКОЙ ОБЛАСТИ"
        )
        assert notice.region == "Московская обл"
        assert notice.platform_name == "РТС-тендер"

    def test_section_price(self) -> None:
        notice = parse_notice_html(_REAL_EIS_HTML)
        assert notice.max_price == Decimal("160926.00")
        assert notice.currency == "RUB"

    def test_section_deadline(self) -> None:
        notice = parse_notice_html(_REAL_EIS_HTML)
        assert notice.application_deadline is not None
        assert notice.application_deadline.year == 2024
        assert notice.application_deadline.month == 2
        assert notice.application_deadline.day == 26
        assert notice.application_deadline.hour == 10

    def test_breadcrumb_reg_number(self) -> None:
        notice = parse_notice_html(_REAL_EIS_HTML)
        assert notice.procurement_number == "0148200005224000001"

    def test_product_table_ignores_characteristic_rows(self) -> None:
        notice = parse_notice_html(_REAL_EIS_HTML)
        assert len(notice.positions) == 2
        names = [p.name for p in notice.positions]
        assert all("характеристик" not in n for n in names)
        assert all(p.okpd2_code == "22.29.26.190" for p in notice.positions)

    def test_product_positions_quantity_price(self) -> None:
        notice = parse_notice_html(_REAL_EIS_HTML)
        first = notice.positions[0]
        assert first.quantity == Decimal("400.00")
        assert first.unit_price == Decimal("296.18")
        assert notice.okpd2_codes == ["22.29.26.190"]


# -----------------------------------------------------------------------
# EIS-03: label/value boundary isolation
# -----------------------------------------------------------------------


class TestEmptyValueBoundary:
    def test_empty_reg_number_does_not_borrow_next_field(self) -> None:
        """'Регистрационный номер' empty, then 'Наименование объекта закупки'
        with a value.  The title must NOT become the registry number."""
        html = """
        <html><body>
        <table>
            <tr><th>Регистрационный номер</th><td></td></tr>
            <tr><th>Наименование объекта закупки</th><td>Поставка станков</td></tr>
        </table>
        </body></html>
        """
        # No breadcrumb, no other reg_number source → EisParseError
        with pytest.raises(Exception, match="registration number"):
            parse_notice_html(html)

    def test_empty_title_does_not_borrow_previous_or_next_field(self) -> None:
        """If a title value is missing, the parser must not accept the
        value of a neighbouring field as the title."""
        html = """
        <html><body>
        <table>
            <tr><th>Регистрационный номер</th><td>0373200049624000001</td></tr>
            <tr><th>Наименование объекта закупки</th><td></td></tr>
            <tr><th>Заказчик</th><td>Пример</td></tr>
        </table>
        </body></html>
        """
        with pytest.raises(Exception, match="title"):
            parse_notice_html(html)

    def test_empty_reg_number_with_breadcrumb_preferred(self) -> None:
        """Empty reg_number field + breadcrumb → use breadcrumb, NOT the
        neighbouring title."""
        html = _make_sections_html(
            '<section class="blockInfo__section section">'
            '    <span class="section__title">Регистрационный номер</span>'
            '    <span class="section__info"></span>'
            "</section>"
            '<section class="blockInfo__section section">'
            '    <span class="section__title">Наименование объекта закупки</span>'
            '    <span class="section__info">Поставка танков</span>'
            "</section>"
        )
        notice = parse_notice_html(html)
        assert notice.procurement_number == "0373200049624000001"
        assert notice.title == "Поставка танков"

    def test_empty_section_info_does_not_consume_next_section(self) -> None:
        """'Регистрационный номер' section with empty info_span followed by
        a 'Наименование объекта закупки' section must not borrow the title."""
        html = _make_sections_html(
            '<section class="blockInfo__section section">'
            '    <span class="section__title">Регистрационный номер</span>'
            '    <span class="section__info">　</span>'
            "</section>"
            '<section class="blockInfo__section section">'
            '    <span class="section__title">Наименование объекта закупки</span>'
            '    <span class="section__info">Поставка сверл</span>'
            "</section>"
        )
        notice = parse_notice_html(html)
        assert notice.procurement_number == "0373200049624000001"
        assert notice.title == "Поставка сверл"

    def test_registry_number_format_is_required(self) -> None:
        """Non-numeric / malformed registry numbers must be rejected even if
        a label is present."""
        html = _make_html(reg_number="123", title="Тест")
        # 123 is too short
        with pytest.raises(EisParseError):
            parse_notice_html(html)


# -----------------------------------------------------------------------
# EIS-04: positions-table selection (must skip generic info table)
# -----------------------------------------------------------------------


class TestPositionsTableSelection:
    def test_generic_table_before_positions_skipped(self) -> None:
        """A generic information table with 'Наименование объекта закупки' and
        a single 'наименование' word precedes the real positions table.
        The parser must select the second table."""
        html = """
        <html><body>
        <table>
            <tr><th>Регистрационный номер</th><td>0373200049624000001</td></tr>
            <tr><th>Наименование объекта закупки</th><td>Оказание услуг</td></tr>
        </table>
        <table class="info-table">
            <thead><tr>
                <th>Наименование объекта закупки</th>
                <th>Значение</th>
            </tr></thead>
            <tbody>
                <tr><td>Наименование объекта закупки</td><td>Оказание услуг</td></tr>
                <tr><td>Заказчик</td><td>Организация</td></tr>
            </tbody>
        </table>
        <table class="positions-table">
            <thead><tr>
                <th>№ п/п</th>
                <th>Код ОКПД2</th>
                <th>Наименование товара, работы, услуги</th>
                <th>Ед. изм.</th>
                <th>Количество</th>
            </tr></thead>
            <tbody>
                <tr><td>1</td><td>28.99.39.190</td>
                <td>Токарные работы по стали</td><td>усл.</td><td>2</td></tr>
            </tbody>
        </table>
        </body></html>
        """
        notice = parse_notice_html(html)
        assert len(notice.positions) == 1
        assert notice.positions[0].name == "Токарные работы по стали"
        assert notice.positions[0].okpd2_code == "28.99.39.190"

    def test_only_generic_table_no_positions_selected(self) -> None:
        """A table with only 'Наименование' (and no structural columns)
        is not a positions table → no positions."""
        html = _make_html() + """
        <table class="info-only">
            <thead><tr><th>Наименование</th></tr></thead>
            <tbody><tr><td>Металлообработка</td></tr></tbody>
        </table>
        """
        notice = parse_notice_html(html)  # must parse OK
        assert notice.positions == []

    def test_okpd2_alone_not_enough(self) -> None:
        """'ОКПД2' word alone (without a name/unit/price column) must not
        trigger positions selection."""
        html = _make_html() + """
        <table>
            <thead><tr><th>ОКПД2</th></tr></thead>
            <tbody><tr><td>25.62.10.000</td></tr></tbody>
        </table>
        """
        notice = parse_notice_html(html)
        assert notice.positions == []


# -----------------------------------------------------------------------
# Full notice parsing
# -----------------------------------------------------------------------


class TestParseNoticeHtml:
    def test_sample_fixture(self, sample_html: str) -> None:
        notice = parse_notice_html(sample_html)
        assert isinstance(notice, ParsedEisNotice)
        assert notice.procurement_number == "0373200049624000001"
        assert "металлообработк" in notice.title.lower()
        assert notice.law == "44-ФЗ"
        assert notice.procurement_method is not None
        assert "котировок" in notice.procurement_method.lower()
        assert notice.customer is not None
        assert notice.platform_name is not None
        assert notice.region is not None
        assert notice.max_price == Decimal("1000000.00")
        assert notice.currency == "RUB"
        assert notice.application_deadline is not None
        assert len(notice.positions) == 6

    def test_positions_okpd2(self, sample_html: str) -> None:
        notice = parse_notice_html(sample_html)
        for pos in notice.positions:
            assert pos.okpd2_code == "25.62.10.000"

    def test_positions_have_names(self, sample_html: str) -> None:
        notice = parse_notice_html(sample_html)
        names = [pos.name for pos in notice.positions]
        assert any("токарн" in n.lower() for n in names)
        assert any("сварочн" in n.lower() for n in names)
        assert any("плазменн" in n.lower() for n in names)

    def test_missing_registration_number_raises(self) -> None:
        html = """
        <html><body>
        <table>
            <tr><th>Наименование</th><td>Тест</td></tr>
        </table>
        </body></html>
        """
        with pytest.raises(Exception, match="registration number"):
            parse_notice_html(html)

    def test_empty_title_raises(self) -> None:
        html = _make_html(title="")
        with pytest.raises(Exception, match="title"):
            parse_notice_html(html)

    def test_minimal_valid_html(self) -> None:
        html = _make_html()
        notice = parse_notice_html(html)
        assert notice.procurement_number == "0373200049624000001"
        assert notice.title == "Тестовая закупка"

    def test_source_url_preserved(self, sample_html: str) -> None:
        url = "https://zakupki.gov.ru/example"
        notice = parse_notice_html(sample_html, source_url=url)
        assert notice.source_url == url

    def test_warranty_extracted(self, sample_html: str) -> None:
        notice = parse_notice_html(sample_html)
        assert notice.quality_warranty is not None
        assert "12" in notice.quality_warranty

    def test_execution_deadline_extracted(self, sample_html: str) -> None:
        notice = parse_notice_html(sample_html)
        assert notice.execution_deadline_text is not None
        assert "12 месяцев" in notice.execution_deadline_text

    def test_delivery_location_extracted(self, sample_html: str) -> None:
        notice = parse_notice_html(sample_html)
        assert notice.delivery_location is not None
        assert "Москва" in notice.delivery_location

    def test_malformed_html_graceful(self) -> None:
        html = "<html><body>Просто текст без структуры</body></html>"
        with pytest.raises(EisParseError):
            parse_notice_html(html)

    def test_empty_table_positions(self) -> None:
        html = (
            _make_html()
            + """
        <table class="positions-table">
            <thead><tr><th>№</th><th>ОКПД2</th><th>Наименование</th></tr></thead>
            <tbody></tbody>
        </table>
        """
        )
        notice = parse_notice_html(html)
        assert notice.positions == []

    def test_positions_with_prices(self) -> None:
        html = (
            _make_html()
            + """
        <table class="positions-table">
            <thead>
                <tr><th>№</th><th>Код ОКПД2</th><th>Наименование</th>
                <th>Ед. изм.</th><th>Количество</th><th>Цена за ед.</th></tr>
            </thead>
            <tbody>
                <tr><td>1</td><td>25.62.10.000</td>
                <td>Работа</td><td>усл.</td><td>5</td><td>10 000,00</td></tr>
            </tbody>
        </table>
        """
        )
        notice = parse_notice_html(html)
        assert len(notice.positions) == 1
        assert notice.positions[0].unit_price == Decimal("10000.00")
        assert notice.positions[0].quantity == Decimal("5")
