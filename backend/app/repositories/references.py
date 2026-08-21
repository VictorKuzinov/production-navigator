
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CompanySize, EquipmentType, Industry, Region
from app.models.base_reference import PNCBaseReference


class ReferenceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_by_code(
            self,
            model: type[PNCBaseReference],
            code: str,
    ) -> PNCBaseReference | None:
        statement = select(model).where(model.code == code)
        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def get_region_by_code(
            self,
            code: str,
    ) -> Region | None:
        return await self._get_by_code(Region, code)

    async def get_company_size_by_code(
            self,
            code: str,
    ) -> CompanySize | None:
        return await self._get_by_code(CompanySize, code)

    async def get_industry_by_code( 
            self,
            code: str,
    ) -> Industry | None:
        return await self._get_by_code(Industry, code)

    async def get_equipment_type_by_code(
        self,
        code: str,
    ) -> EquipmentType | None:
        return await self._get_by_code(EquipmentType, code)

