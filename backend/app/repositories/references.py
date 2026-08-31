
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CompanySize,
    CraneType,
    EquipmentType,
    Industry,
    MaterialForm,
    MaterialGroup,
    ProductType,
    Region,
    TransportOwnershipType,
    TransportScope,
    TransportType,
    WarehouseType,
)
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

    async def get_material_group_by_code(
        self,
        code: str,
    ) -> MaterialGroup | None:
        return await self._get_by_code(MaterialGroup, code)

    async def get_material_form_by_code(
        self,
        code: str,
    ) -> MaterialForm | None:
        return await self._get_by_code(MaterialForm, code)

    async def get_product_type_by_code(
        self,
        code: str,
    ) -> ProductType | None:
        return await self._get_by_code(ProductType, code)

    async def get_warehouse_type_by_code(
        self,
        code: str,
    ) -> WarehouseType | None:
        return await self._get_by_code(WarehouseType, code)

    async def get_crane_type_by_code(
        self,
        code: str,
    ) -> CraneType | None:
        return await self._get_by_code(CraneType, code)

    async def get_transport_type_by_code(
        self,
        code: str,
    ) -> TransportType | None:
        return await self._get_by_code(TransportType, code)

    async def get_transport_scope_by_code(
        self,
        code: str,
    ) -> TransportScope | None:
        return await self._get_by_code(TransportScope, code)

    async def get_transport_ownership_type_by_code(
        self,
        code: str,
    ) -> TransportOwnershipType | None:
        return await self._get_by_code(TransportOwnershipType, code)
