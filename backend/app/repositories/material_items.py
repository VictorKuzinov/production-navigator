from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MaterialItem, Product
from app.schemas import MaterialItemCreate, MaterialItemUpdate


class MaterialItemRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(
        self,
        material_item_id: int,
    ) -> MaterialItem | None:
        statement = select(MaterialItem).where(MaterialItem.id == material_item_id)
        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def get_by_identity(
        self,
        material_id: int,
        material_form_code: str,
        dimension_1: float | None,
        unit_of_measure: str,
    ) -> MaterialItem | None:
        dimension_filter = (
            MaterialItem.dimension_1.is_(None)
            if dimension_1 is None
            else MaterialItem.dimension_1 == dimension_1
        )
        statement = select(MaterialItem).where(
            MaterialItem.material_id == material_id,
            MaterialItem.material_form_code == material_form_code,
            dimension_filter,
            MaterialItem.unit_of_measure == unit_of_measure,
        )
        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def list_material_items(self) -> list[MaterialItem]:
        statement = select(MaterialItem).order_by(MaterialItem.id)
        result = await self.session.execute(statement)

        return list(result.scalars().all())

    async def has_products(self, material_item_id: int) -> bool:
        statement = (
            select(Product.id)
            .where(Product.material_item_id == material_item_id)
            .limit(1)
        )
        result = await self.session.execute(statement)

        return result.scalar_one_or_none() is not None

    async def create(self, data: MaterialItemCreate) -> MaterialItem:
        material_item = MaterialItem(**data.model_dump())
        self.session.add(material_item)

        await self.session.commit()
        await self.session.refresh(material_item)

        return material_item

    async def update(
        self,
        material_item_id: int,
        data: MaterialItemUpdate,
    ) -> MaterialItem | None:
        material_item = await self.get_by_id(material_item_id)
        if material_item is None:
            return None

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(material_item, field, value)

        await self.session.commit()
        await self.session.refresh(material_item)

        return material_item

    async def delete(
        self,
        material_item_id: int,
    ) -> MaterialItem | None:
        material_item = await self.get_by_id(material_item_id)
        if material_item is None:
            return None

        await self.session.delete(material_item)
        await self.session.commit()

        return material_item
