from datetime import date, datetime

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.procurement_opportunities import (
    ProcurementCertificateRequirement,
    ProcurementEquipmentRequirement,
    ProcurementMaterialRequirement,
    ProcurementOpportunity,
    ProcurementOpportunityProductType,
    ProcurementTechnologyRequirement,
    RequirementCollectionState,
)
from app.schemas.procurement_opportunities import (
    Deadline,
    PreparedOpportunityInput,
    canonical_payload,
    canonicalize_opportunity,
)

type ProcurementOpportunityIdentity = tuple[str, str]


class ProcurementOpportunityRepository:
    """Aggregate persistence with flush-only transaction semantics."""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _load_options():
        return (
            selectinload(ProcurementOpportunity.product_types),
            selectinload(ProcurementOpportunity.material_requirements),
            selectinload(ProcurementOpportunity.technology_requirements),
            selectinload(ProcurementOpportunity.equipment_requirements),
            selectinload(ProcurementOpportunity.certificate_requirements),
        )

    async def get_by_identity(
        self,
        source: str,
        external_id: str,
    ) -> ProcurementOpportunity | None:
        statement = (
            select(ProcurementOpportunity)
            .where(
                ProcurementOpportunity.source == source,
                ProcurementOpportunity.external_id == external_id,
            )
            .options(*self._load_options())
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_identities(
        self,
        identities: list[ProcurementOpportunityIdentity],
    ) -> dict[ProcurementOpportunityIdentity, ProcurementOpportunity]:
        if not identities:
            return {}
        statement = (
            select(ProcurementOpportunity)
            .where(
                tuple_(
                    ProcurementOpportunity.source,
                    ProcurementOpportunity.external_id,
                ).in_(identities)
            )
            .options(*self._load_options())
            .order_by(
                ProcurementOpportunity.source,
                ProcurementOpportunity.external_id,
            )
        )
        result = await self.session.execute(statement)
        opportunities = result.scalars().all()
        return {
            (opportunity.source, opportunity.external_id): opportunity
            for opportunity in opportunities
        }

    async def list_all(self) -> list[ProcurementOpportunity]:
        statement = (
            select(ProcurementOpportunity)
            .options(*self._load_options())
            .order_by(
                ProcurementOpportunity.source,
                ProcurementOpportunity.external_id,
            )
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def create_from_canonical(
        self,
        record: PreparedOpportunityInput,
    ) -> ProcurementOpportunity:
        record = canonicalize_opportunity(record)
        opportunity = ProcurementOpportunity(
            source=record.source,
            external_id=record.external_id,
        )
        self._assign_parent_snapshot(opportunity, record)
        self._assign_children(opportunity, record)
        self.session.add(opportunity)
        await self.session.flush()
        return opportunity

    async def replace_snapshot(
        self,
        opportunity: ProcurementOpportunity,
        record: PreparedOpportunityInput,
    ) -> ProcurementOpportunity:
        record = canonicalize_opportunity(record)
        self._assign_parent_snapshot(opportunity, record)

        opportunity.product_types.clear()
        opportunity.material_requirements.clear()
        opportunity.technology_requirements.clear()
        opportunity.equipment_requirements.clear()
        opportunity.certificate_requirements.clear()
        await self.session.flush()

        self._assign_children(opportunity, record)
        await self.session.flush()
        return opportunity

    @staticmethod
    def _collection_state(items: list[object] | None) -> RequirementCollectionState:
        if items is None:
            return RequirementCollectionState.UNKNOWN
        return RequirementCollectionState.KNOWN

    @staticmethod
    def _deadline_columns(value: Deadline) -> tuple[date | None, datetime | None]:
        if isinstance(value, datetime):
            return None, value
        return value, None

    def _assign_parent_snapshot(
        self,
        opportunity: ProcurementOpportunity,
        record: PreparedOpportunityInput,
    ) -> None:
        payload = canonical_payload(record)
        application_date, application_at = self._deadline_columns(
            record.application_deadline
        )
        execution_date, execution_at = self._deadline_columns(record.execution_deadline)

        opportunity.procurement_number = record.procurement_number
        opportunity.title = record.title
        opportunity.customer = record.customer
        opportunity.source_url = record.source_url
        opportunity.status = record.status
        opportunity.procurement_type = record.procurement_type
        opportunity.okpd2_codes = payload["okpd2_codes"]
        opportunity.product_type_codes_state = self._collection_state(
            record.product_type_codes
        )
        opportunity.material_requirements_state = self._collection_state(
            record.material_requirements
        )
        opportunity.technology_requirements_state = self._collection_state(
            record.technology_requirements
        )
        opportunity.equipment_requirements_state = self._collection_state(
            record.equipment_requirements
        )
        opportunity.required_certificates_state = self._collection_state(
            record.required_certificates
        )
        opportunity.dimensional_mass_requirements = payload[
            "dimensional_mass_requirements"
        ]
        opportunity.quality_requirements = payload["quality_requirements"]
        opportunity.price_amount = record.price_amount
        opportunity.price_currency = record.price_currency
        opportunity.region_code = record.region_code
        opportunity.quantity = record.quantity
        opportunity.unit = record.unit
        opportunity.application_deadline_date = application_date
        opportunity.application_deadline_at = application_at
        opportunity.execution_deadline_date = execution_date
        opportunity.execution_deadline_at = execution_at

    @staticmethod
    def _assign_children(
        opportunity: ProcurementOpportunity,
        record: PreparedOpportunityInput,
    ) -> None:
        opportunity.product_types = [
            ProcurementOpportunityProductType(product_type_code=code)
            for code in record.product_type_codes or []
        ]
        opportunity.material_requirements = [
            ProcurementMaterialRequirement(
                material_group_code=item.material_group_code,
                material_id=item.material_id,
                requirement_strength=item.requirement_strength,
            )
            for item in record.material_requirements or []
        ]
        opportunity.technology_requirements = [
            ProcurementTechnologyRequirement(
                technology_code=item.technology_code,
                requirement_strength=item.requirement_strength,
            )
            for item in record.technology_requirements or []
        ]
        opportunity.equipment_requirements = [
            ProcurementEquipmentRequirement(
                equipment_type_code=item.equipment_type_code,
                cnc=item.cnc,
                axes=item.axes,
                working_zone_x_mm=item.working_zone_x_mm,
                working_zone_y_mm=item.working_zone_y_mm,
                working_zone_z_mm=item.working_zone_z_mm,
                diameter_mm=item.diameter_mm,
                requirement_strength=item.requirement_strength,
            )
            for item in record.equipment_requirements or []
        ]
        opportunity.certificate_requirements = [
            ProcurementCertificateRequirement(
                certificate_type_code=item.certificate_type_code,
                requirement_strength=item.requirement_strength,
                required_by=item.required_by,
                valid_through=item.valid_through,
            )
            for item in record.required_certificates or []
        ]
