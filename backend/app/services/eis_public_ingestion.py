"""Оркестрация импорта одной публичной закупки 44-ФЗ из ЕИС."""

from __future__ import annotations

from app.schemas.procurement_opportunities import (
    ProcurementOpportunityIngestionResult,
)
from app.services.procurement_opportunities import (
    ProcurementOpportunityIngestionService,
)
from app.sources.eis_public import (
    fetch_and_parse_notice,
    project_to_prepared_input,
)


class EisPublicOpportunityIngestionService:
    """Соединяет публичный адаптер ЕИС с существующим ingestion закупок."""

    def __init__(
        self,
        ingestion_service: ProcurementOpportunityIngestionService,
    ) -> None:
        """Сохраняет существующий ingestion service как единственную зависимость."""
        self.ingestion_service = ingestion_service

    async def ingest_by_registration_number(
        self,
        registration_number: str,
    ) -> ProcurementOpportunityIngestionResult:
        """Загружает и сохраняет одну закупку ЕИС по регистрационному номеру.

        Transport, parser и projector используются без дополнительной
        validation или преобразования exceptions. CREATE, UPDATE, NO-OP,
        transaction и persistence остаются ответственностью существующего
        ProcurementOpportunityIngestionService.
        """
        notice = await fetch_and_parse_notice(reg_number=registration_number)
        prepared_input = project_to_prepared_input(notice)
        return await self.ingestion_service.ingest_batch([prepared_input])