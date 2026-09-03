from decimal import Decimal, InvalidOperation

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import CapabilitySectionIntegrityError
from app.models.enterprises import EnterpriseProfile
from app.models.profile_capabilities import ProfileSectionCode
from app.schemas.procurement_matching import (
    CertificateSnapshot,
    EquipmentSnapshot,
    MaterialCapabilitySnapshot,
    ProductExperienceSnapshot,
    ProfileMatchingSnapshot,
    QualityCapabilitySnapshot,
    TechnologyCapabilitySnapshot,
)


class ProfileMatchingProjectionRepository:
    """Read-only materializer for the pure matching engine."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, profile_id: int) -> ProfileMatchingSnapshot | None:
        statement = (
            select(EnterpriseProfile)
            .where(EnterpriseProfile.id == profile_id)
            .options(
                selectinload(EnterpriseProfile.products),
                selectinload(EnterpriseProfile.technology_capabilities),
                selectinload(EnterpriseProfile.material_capabilities),
                selectinload(EnterpriseProfile.capability_sections),
                selectinload(EnterpriseProfile.equipments),
                selectinload(EnterpriseProfile.quality_capability),
                selectinload(EnterpriseProfile.certificates),
            )
            .execution_options(autoflush=False)
        )
        with self.session.no_autoflush:
            result = await self.session.execute(statement)
            profile = result.scalar_one_or_none()
        if profile is None:
            return None
        return self._project(profile)

    @classmethod
    def _project(cls, profile: EnterpriseProfile) -> ProfileMatchingSnapshot:
        sections = {row.section_code: row.state for row in profile.capability_sections}
        required_sections = {
            ProfileSectionCode.TECHNOLOGIES,
            ProfileSectionCode.MATERIALS,
        }
        if set(sections) != required_sections:
            missing = sorted(code.value for code in required_sections - set(sections))
            extra = sorted(str(code) for code in set(sections) - required_sections)
            details = []
            if missing:
                details.append(f"missing={missing}")
            if extra:
                details.append(f"unexpected={extra}")
            raise CapabilitySectionIntegrityError(
                f"Profile {profile.id} capability sections are invalid "
                f"({', '.join(details)})."
            )

        try:
            quality = None
            if profile.quality_capability is not None:
                row = profile.quality_capability
                quality = QualityCapabilitySnapshot(
                    capability_id=row.id,
                    min_it_grade=row.min_it_grade,
                    min_ra=cls._finite_decimal(row.min_ra, "quality.min_ra"),
                    measuring_tools=row.measuring_tools,
                    cim_machine=row.cim_machine,
                )
            return ProfileMatchingSnapshot(
                profile_id=profile.id,
                products=tuple(
                    ProductExperienceSnapshot(
                        product_id=row.id,
                        product_type_code=row.product_type_code,
                    )
                    for row in sorted(
                        profile.products,
                        key=lambda item: (item.product_type_code, item.id),
                    )
                ),
                technology_capabilities=tuple(
                    TechnologyCapabilitySnapshot(
                        capability_id=row.id,
                        technology_code=row.technology_code,
                        state=row.state,
                    )
                    for row in sorted(
                        profile.technology_capabilities,
                        key=lambda item: (item.technology_code, item.id),
                    )
                ),
                material_capabilities=tuple(
                    MaterialCapabilitySnapshot(
                        capability_id=row.id,
                        material_group_code=row.material_group_code,
                        material_id=row.material_id,
                        state=row.state,
                    )
                    for row in sorted(
                        profile.material_capabilities,
                        key=lambda item: (
                            item.material_group_code or "",
                            item.material_id or -1,
                            item.id,
                        ),
                    )
                ),
                technology_section_state=sections[ProfileSectionCode.TECHNOLOGIES],
                material_section_state=sections[ProfileSectionCode.MATERIALS],
                equipments=tuple(
                    EquipmentSnapshot(
                        equipment_id=row.id,
                        equipment_type_code=row.equipment_type_code,
                        cnc=row.cnc,
                        axes=row.axes,
                        quantity=row.quantity,
                        max_diameter=cls._finite_decimal(
                            row.max_diameter,
                            "equipment.max_diameter",
                        ),
                        working_zone_x=cls._finite_decimal(
                            row.working_zone_x,
                            "equipment.working_zone_x",
                        ),
                        working_zone_y=cls._finite_decimal(
                            row.working_zone_y,
                            "equipment.working_zone_y",
                        ),
                        working_zone_z=cls._finite_decimal(
                            row.working_zone_z,
                            "equipment.working_zone_z",
                        ),
                    )
                    for row in sorted(
                        profile.equipments,
                        key=lambda item: (item.equipment_type_code, item.id),
                    )
                ),
                quality_capability=quality,
                certificates=tuple(
                    CertificateSnapshot(
                        certificate_id=row.id,
                        certificate_type_code=row.certificate_type_code,
                        issue_date=row.issue_date,
                        expiry_date=row.expiry_date,
                    )
                    for row in sorted(
                        profile.certificates,
                        key=lambda item: (
                            item.certificate_type_code,
                            item.issue_date,
                            item.expiry_date,
                            item.id,
                        ),
                    )
                ),
            )
        except (ValidationError, ValueError, TypeError) as exc:
            raise CapabilitySectionIntegrityError(
                f"Profile {profile.id} cannot be projected for matching."
            ) from exc

    @staticmethod
    def _finite_decimal(value: float | None, field_name: str) -> Decimal | None:
        if value is None:
            return None
        try:
            result = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError(f"{field_name} is not a valid decimal.") from exc
        if not result.is_finite():
            raise ValueError(f"{field_name} must be finite.")
        return result
