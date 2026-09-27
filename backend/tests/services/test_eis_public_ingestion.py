"""Тесты оркестрации импорта одной публичной закупки из ЕИС."""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.eis_public_ingestion as ingestion_module
import app.sources.eis_public as eis_public_source
from app.repositories import (
    MaterialRepository,
    ProcurementOpportunityRepository,
    ReferenceRepository,
)
from app.schemas.procurement_opportunities import (
    PreparedOpportunityInput,
    ProcurementOpportunityIngestionResult,
)
from app.services.eis_public_ingestion import (
    EisPublicOpportunityIngestionService,
)
from app.services.procurement_opportunities import (
    ProcurementOpportunityIngestionService,
)
from app.sources.eis_public import (
    EisParseError,
    EisProjectionError,
    EisTransportError,
    ParsedEisNotice,
)

REGISTRATION_NUMBER = "0373200049624000001"


def _notice_html(
    *,
    title: str = "Поставка крепежа",
) -> str:
    """Возвращает минимальный HTML одной закупки с валидным ОКПД2."""
    return f"""
    <html>
      <body>
        <table>
          <tr>
            <th>Регистрационный номер</th>
            <td>{REGISTRATION_NUMBER}</td>
          </tr>
          <tr>
            <th>Наименование объекта закупки</th>
            <td>{title}</td>
          </tr>
        </table>
        <table class="positions-table">
          <thead>
            <tr>
              <th>№</th>
              <th>Код ОКПД2</th>
              <th>Наименование</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>1</td>
              <td>25.62.10.000</td>
              <td>Крепежные изделия</td>
            </tr>
          </tbody>
        </table>
      </body>
    </html>
    """


def _patch_transport(
    monkeypatch: pytest.MonkeyPatch,
    html: str,
) -> None:
    """Подменяет только сетевую границу, сохраняя реальные parser и projector."""

    async def fake_fetch_notice(
        reg_number: str,
        **_kwargs: object,
    ) -> tuple[str, str]:
        """Возвращает подготовленный HTML вместо обращения к публичной ЕИС."""
        url = (
            "https://zakupki.gov.ru/epz/order/notice/ea20/"
            f"view/common-info.html?regNumber={reg_number}"
        )
        return html, url

    monkeypatch.setattr(
        eis_public_source,
        "fetch_notice_by_reg_number",
        fake_fetch_notice,
    )


def _build_service(
    db_session: AsyncSession,
) -> tuple[
    EisPublicOpportunityIngestionService,
    ProcurementOpportunityRepository,
]:
    """Собирает proposed orchestration поверх существующего ingestion."""
    repository = ProcurementOpportunityRepository(db_session)
    ingestion_service = ProcurementOpportunityIngestionService(
        session=db_session,
        opportunity_repository=repository,
        reference_repository=ReferenceRepository(db_session),
        material_repository=MaterialRepository(db_session),
    )
    return (
        EisPublicOpportunityIngestionService(ingestion_service),
        repository,
    )


async def test_registration_number_flow_creates_opportunity(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Полный flow создаёт одну ProcurementOpportunity с identity ЕИС."""
    _patch_transport(monkeypatch, _notice_html())
    service, repository = _build_service(db_session)

    result = await service.ingest_by_registration_number(
        REGISTRATION_NUMBER
    )

    stored = await repository.get_by_identity(
        "eis_public_44fz",
        REGISTRATION_NUMBER,
    )
    assert result.created == 1
    assert result.updated == 0
    assert result.unchanged == 0
    assert stored is not None
    assert stored.procurement_number == REGISTRATION_NUMBER
    assert stored.title == "Поставка крепежа"
    assert stored.okpd2_codes == ["25.62.10.000"]


async def test_same_notice_is_noop(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Повторный импорт неизменённой закупки возвращает NO-OP."""
    _patch_transport(monkeypatch, _notice_html())
    service, _repository = _build_service(db_session)

    first = await service.ingest_by_registration_number(
        REGISTRATION_NUMBER
    )
    second = await service.ingest_by_registration_number(
        REGISTRATION_NUMBER
    )

    assert first.created == 1
    assert second.created == 0
    assert second.updated == 0
    assert second.unchanged == 1


async def test_changed_notice_updates_existing_identity(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Изменённый snapshot обновляет запись без смены database identity."""
    _patch_transport(monkeypatch, _notice_html())
    service, repository = _build_service(db_session)
    await service.ingest_by_registration_number(REGISTRATION_NUMBER)

    original = await repository.get_by_identity(
        "eis_public_44fz",
        REGISTRATION_NUMBER,
    )
    assert original is not None
    original_id = original.id

    _patch_transport(
        monkeypatch,
        _notice_html(title="Поставка крепежа (изменено)"),
    )
    result = await service.ingest_by_registration_number(
        REGISTRATION_NUMBER
    )

    updated = await repository.get_by_identity(
        "eis_public_44fz",
        REGISTRATION_NUMBER,
    )
    assert result.created == 0
    assert result.updated == 1
    assert result.unchanged == 0
    assert updated is not None
    assert updated.id == original_id
    assert updated.title == "Поставка крепежа (изменено)"


async def test_transport_error_is_not_masked(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Transport error проходит через orchestration без замены."""
    expected = EisTransportError("transport failed")

    async def fail_transport(
        _reg_number: str,
        **_kwargs: object,
    ) -> tuple[str, str]:
        """Имитирует отказ существующего transport."""
        raise expected

    monkeypatch.setattr(
        eis_public_source,
        "fetch_notice_by_reg_number",
        fail_transport,
    )
    service, _repository = _build_service(db_session)

    with pytest.raises(EisTransportError) as caught:
        await service.ingest_by_registration_number(REGISTRATION_NUMBER)

    assert caught.value is expected


async def test_parser_error_is_not_masked(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parser error проходит через orchestration без замены."""
    _patch_transport(
        monkeypatch,
        "<html><body>Страница без полей закупки</body></html>",
    )
    service, _repository = _build_service(db_session)

    with pytest.raises(EisParseError):
        await service.ingest_by_registration_number(REGISTRATION_NUMBER)


async def test_projector_error_is_not_masked(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Projector error проходит через orchestration без замены."""
    _patch_transport(monkeypatch, _notice_html())
    expected = EisProjectionError("projection failed")

    def fail_projection(
        _notice: ParsedEisNotice,
    ) -> PreparedOpportunityInput:
        """Имитирует отказ существующего projector."""
        raise expected

    monkeypatch.setattr(
        ingestion_module,
        "project_to_prepared_input",
        fail_projection,
    )
    service, _repository = _build_service(db_session)

    with pytest.raises(EisProjectionError) as caught:
        await service.ingest_by_registration_number(REGISTRATION_NUMBER)

    assert caught.value is expected


async def test_ingestion_error_is_not_masked(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ошибка existing ingestion проходит через orchestration без замены."""
    _patch_transport(monkeypatch, _notice_html())
    service, _repository = _build_service(db_session)
    expected = RuntimeError("ingestion failed")

    async def fail_ingestion(
        _records: Sequence[PreparedOpportunityInput],
    ) -> ProcurementOpportunityIngestionResult:
        """Имитирует отказ существующего ingestion service."""
        raise expected

    monkeypatch.setattr(
        service.ingestion_service,
        "ingest_batch",
        fail_ingestion,
    )

    with pytest.raises(RuntimeError) as caught:
        await service.ingest_by_registration_number(REGISTRATION_NUMBER)

    assert caught.value is expected