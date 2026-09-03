from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ProcurementOpportunityBatchConflictError,
    ProcurementOpportunityIntegrityError,
    ProcurementOpportunityReferenceError,
)
from app.models.procurement_opportunities import (
    ProcurementOpportunity,
    RequirementCollectionState,
)
from app.repositories.materials import MaterialRepository
from app.repositories.procurement_opportunities import (
    ProcurementOpportunityIdentity,
    ProcurementOpportunityRepository,
)
from app.repositories.references import ReferenceRepository
from app.schemas.procurement_opportunities import (
    PreparedOpportunityInput,
    ProcurementOpportunityIngestionResult,
    canonical_payload_json,
    canonicalize_opportunity,
)


class ProcurementOpportunityIngestionService:
    def __init__(
        self,
        session: AsyncSession,
        opportunity_repository: ProcurementOpportunityRepository,
        reference_repository: ReferenceRepository,
        material_repository: MaterialRepository,
    ):
        self.session = session
        self.opportunity_repository = opportunity_repository
        self.reference_repository = reference_repository
        self.material_repository = material_repository

    async def ingest_batch(
        self,
        records: Sequence[PreparedOpportunityInput],
    ) -> ProcurementOpportunityIngestionResult:
        if not records:
            raise ValueError("A procurement opportunity batch must not be empty.")

        canonical_records, duplicate_rows = self._collapse_batch(records)
        identities = sorted(canonical_records)

        try:
            await self._validate_references(canonical_records)
            existing = await self.opportunity_repository.get_by_identities(identities)

            created = 0
            updated = 0
            unchanged = 0
            for identity in identities:
                record = canonical_records[identity]
                opportunity = existing.get(identity)
                if opportunity is None:
                    await self.opportunity_repository.create_from_canonical(record)
                    created += 1
                    continue

                saved_record = self._canonical_from_aggregate(opportunity)
                if canonical_payload_json(saved_record) == canonical_payload_json(
                    record
                ):
                    unchanged += 1
                    continue

                await self.opportunity_repository.replace_snapshot(
                    opportunity,
                    record,
                )
                updated += 1

            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ProcurementOpportunityIntegrityError(
                "The procurement opportunity batch violated database integrity."
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

        return ProcurementOpportunityIngestionResult(
            received_rows=len(records),
            unique_identities=len(canonical_records),
            created=created,
            updated=updated,
            unchanged=unchanged,
            duplicate_rows=duplicate_rows,
        )

    @staticmethod
    def _collapse_batch(
        records: Sequence[PreparedOpportunityInput],
    ) -> tuple[
        dict[ProcurementOpportunityIdentity, PreparedOpportunityInput],
        int,
    ]:
        grouped: dict[
            ProcurementOpportunityIdentity,
            list[tuple[int, PreparedOpportunityInput, str]],
        ] = defaultdict(list)
        for position, input_record in enumerate(records, start=1):
            record = canonicalize_opportunity(input_record)
            identity = (record.source, record.external_id)
            grouped[identity].append((position, record, canonical_payload_json(record)))

        conflicts: list[tuple[str, str, tuple[int, ...]]] = []
        canonical_records: dict[
            ProcurementOpportunityIdentity,
            PreparedOpportunityInput,
        ] = {}
        duplicate_rows = 0
        for identity in sorted(grouped):
            candidates = grouped[identity]
            payloads = {payload for _, _, payload in candidates}
            if len(payloads) > 1:
                conflicts.append(
                    (
                        identity[0],
                        identity[1],
                        tuple(sorted(position for position, _, _ in candidates)),
                    )
                )
                continue
            canonical_records[identity] = min(
                candidates,
                key=lambda candidate: candidate[0],
            )[1]
            duplicate_rows += len(candidates) - 1

        if conflicts:
            raise ProcurementOpportunityBatchConflictError(tuple(conflicts))
        return canonical_records, duplicate_rows

    async def _validate_references(
        self,
        records: dict[
            ProcurementOpportunityIdentity,
            PreparedOpportunityInput,
        ],
    ) -> None:
        region_uses: dict[str, set[ProcurementOpportunityIdentity]] = defaultdict(set)
        product_uses: dict[str, set[ProcurementOpportunityIdentity]] = defaultdict(set)
        group_uses: dict[str, set[ProcurementOpportunityIdentity]] = defaultdict(set)
        technology_uses: dict[str, set[ProcurementOpportunityIdentity]] = defaultdict(
            set
        )
        equipment_uses: dict[str, set[ProcurementOpportunityIdentity]] = defaultdict(
            set
        )
        certificate_uses: dict[str, set[ProcurementOpportunityIdentity]] = defaultdict(
            set
        )
        material_uses: dict[tuple[int, str], set[ProcurementOpportunityIdentity]] = (
            defaultdict(set)
        )

        for identity in sorted(records):
            record = records[identity]
            if record.region_code is not None:
                region_uses[record.region_code].add(identity)
            for code in record.product_type_codes or []:
                product_uses[code].add(identity)
            for item in record.material_requirements or []:
                group_uses[item.material_group_code].add(identity)
                if item.material_id is not None:
                    material_uses[(item.material_id, item.material_group_code)].add(
                        identity
                    )
            for item in record.technology_requirements or []:
                technology_uses[item.technology_code].add(identity)
            for item in record.equipment_requirements or []:
                equipment_uses[item.equipment_type_code].add(identity)
            for item in record.required_certificates or []:
                certificate_uses[item.certificate_type_code].add(identity)

        issues: set[tuple[str, str, str]] = set()

        async def check_codes(uses, lookup, label: str) -> None:
            for code in sorted(uses):
                if await lookup(code) is not None:
                    continue
                for source, external_id in sorted(uses[code]):
                    issues.add(
                        (
                            source,
                            external_id,
                            f"{label} {code!r} was not found",
                        )
                    )

        await check_codes(
            region_uses,
            self.reference_repository.get_region_by_code,
            "region_code",
        )
        await check_codes(
            product_uses,
            self.reference_repository.get_product_type_by_code,
            "product_type_code",
        )
        await check_codes(
            group_uses,
            self.reference_repository.get_material_group_by_code,
            "material_group_code",
        )

        materials: dict[int, Any] = {}
        for material_id in sorted({target[0] for target in material_uses}):
            materials[material_id] = await self.material_repository.get_by_id(
                material_id
            )
        for (material_id, group_code), identities in sorted(material_uses.items()):
            material = materials[material_id]
            if material is None:
                reason = f"material_id {material_id} was not found"
            elif material.group_code != group_code:
                reason = (
                    f"material_id {material_id} belongs to group "
                    f"{material.group_code!r}, not {group_code!r}"
                )
            else:
                continue
            for source, external_id in sorted(identities):
                issues.add((source, external_id, reason))

        await check_codes(
            technology_uses,
            self.reference_repository.get_technology_type_by_code,
            "technology_code",
        )
        await check_codes(
            equipment_uses,
            self.reference_repository.get_equipment_type_by_code,
            "equipment_type_code",
        )
        await check_codes(
            certificate_uses,
            self.reference_repository.get_certificate_type_by_code,
            "certificate_type_code",
        )

        if issues:
            raise ProcurementOpportunityReferenceError(tuple(sorted(issues)))

    @staticmethod
    def _stateful_collection(
        opportunity: ProcurementOpportunity,
        state_value: object,
        values: list[dict[str, Any]] | list[str],
        field_name: str,
    ) -> list[dict[str, Any]] | list[str] | None:
        try:
            state = RequirementCollectionState(state_value)
        except ValueError as exc:
            raise ProcurementOpportunityIntegrityError(
                f"Stored opportunity ({opportunity.source}, "
                f"{opportunity.external_id}) has invalid {field_name} state."
            ) from exc
        if state == RequirementCollectionState.UNKNOWN:
            if values:
                raise ProcurementOpportunityIntegrityError(
                    f"Stored opportunity ({opportunity.source}, "
                    f"{opportunity.external_id}) has UNKNOWN {field_name} "
                    "with child rows."
                )
            return None
        return values

    @staticmethod
    def _decimal_for_input(value: Decimal | None, places: int) -> str | None:
        if value is None:
            return None
        return f"{value:.{places}f}"

    @staticmethod
    def _deadline_from_columns(
        opportunity: ProcurementOpportunity,
        date_value: date | None,
        datetime_value: datetime | None,
        field_name: str,
    ) -> date | datetime | None:
        if date_value is not None and datetime_value is not None:
            raise ProcurementOpportunityIntegrityError(
                f"Stored opportunity ({opportunity.source}, "
                f"{opportunity.external_id}) has both physical columns for "
                f"{field_name}."
            )
        if datetime_value is not None:
            if datetime_value.tzinfo is None:
                datetime_value = datetime_value.replace(tzinfo=UTC)
            return datetime_value.astimezone(UTC)
        return date_value

    def _canonical_from_aggregate(
        self,
        opportunity: ProcurementOpportunity,
    ) -> PreparedOpportunityInput:
        product_types = self._stateful_collection(
            opportunity,
            opportunity.product_type_codes_state,
            [item.product_type_code for item in opportunity.product_types],
            "product_type_codes",
        )
        materials = self._stateful_collection(
            opportunity,
            opportunity.material_requirements_state,
            [
                {
                    "material_group_code": item.material_group_code,
                    "material_id": item.material_id,
                    "requirement_strength": item.requirement_strength,
                }
                for item in opportunity.material_requirements
            ],
            "material_requirements",
        )
        technologies = self._stateful_collection(
            opportunity,
            opportunity.technology_requirements_state,
            [
                {
                    "technology_code": item.technology_code,
                    "requirement_strength": item.requirement_strength,
                }
                for item in opportunity.technology_requirements
            ],
            "technology_requirements",
        )
        equipment = self._stateful_collection(
            opportunity,
            opportunity.equipment_requirements_state,
            [
                {
                    "equipment_type_code": item.equipment_type_code,
                    "cnc": item.cnc,
                    "axes": item.axes,
                    "working_zone_x_mm": self._decimal_for_input(
                        item.working_zone_x_mm,
                        3,
                    ),
                    "working_zone_y_mm": self._decimal_for_input(
                        item.working_zone_y_mm,
                        3,
                    ),
                    "working_zone_z_mm": self._decimal_for_input(
                        item.working_zone_z_mm,
                        3,
                    ),
                    "diameter_mm": self._decimal_for_input(item.diameter_mm, 3),
                    "requirement_strength": item.requirement_strength,
                }
                for item in opportunity.equipment_requirements
            ],
            "equipment_requirements",
        )
        certificates = self._stateful_collection(
            opportunity,
            opportunity.required_certificates_state,
            [
                {
                    "certificate_type_code": item.certificate_type_code,
                    "requirement_strength": item.requirement_strength,
                    "required_by": item.required_by,
                    "valid_through": item.valid_through,
                }
                for item in opportunity.certificate_requirements
            ],
            "required_certificates",
        )

        payload = {
            "source": opportunity.source,
            "external_id": opportunity.external_id,
            "procurement_number": opportunity.procurement_number,
            "title": opportunity.title,
            "customer": opportunity.customer,
            "source_url": opportunity.source_url,
            "status": opportunity.status,
            "procurement_type": opportunity.procurement_type,
            "okpd2_codes": opportunity.okpd2_codes,
            "product_type_codes": product_types,
            "price_amount": self._decimal_for_input(opportunity.price_amount, 2),
            "price_currency": opportunity.price_currency,
            "region_code": opportunity.region_code,
            "quantity": self._decimal_for_input(opportunity.quantity, 6),
            "unit": opportunity.unit,
            "application_deadline": self._deadline_from_columns(
                opportunity,
                opportunity.application_deadline_date,
                opportunity.application_deadline_at,
                "application_deadline",
            ),
            "execution_deadline": self._deadline_from_columns(
                opportunity,
                opportunity.execution_deadline_date,
                opportunity.execution_deadline_at,
                "execution_deadline",
            ),
            "material_requirements": materials,
            "technology_requirements": technologies,
            "equipment_requirements": equipment,
            "dimensional_mass_requirements": (
                opportunity.dimensional_mass_requirements
            ),
            "quality_requirements": opportunity.quality_requirements,
            "required_certificates": certificates,
        }
        try:
            return canonicalize_opportunity(
                PreparedOpportunityInput.model_validate(payload)
            )
        except (ValidationError, TypeError, ValueError) as exc:
            raise ProcurementOpportunityIntegrityError(
                f"Stored opportunity ({opportunity.source}, "
                f"{opportunity.external_id}) cannot be projected canonically."
            ) from exc
