from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Material, MaterialItem
from app.schemas import MaterialCreate, MaterialUpdate


class MaterialRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(
        self,
        material_id: int,
    ) -> Material | None:
        statement = select(Material).where(Material.id == material_id)
        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def get_by_group_and_grade(
        self,
        group_code: str,
        grade_name: str,
    ) -> Material | None:
        statement = select(Material).where(
            Material.group_code == group_code,
            Material.grade_name == grade_name,
        )
        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def list_materials(self) -> list[Material]:
        statement = select(Material).order_by(Material.id)
        result = await self.session.execute(statement)

        return list(result.scalars().all())

    async def has_material_items(self, material_id: int) -> bool:
        statement = (
            select(MaterialItem.id)
            .where(MaterialItem.material_id == material_id)
            .limit(1)
        )
        result = await self.session.execute(statement)

        return result.scalar_one_or_none() is not None

    async def create(self, data: MaterialCreate) -> Material:
        material = Material(**data.model_dump())
        self.session.add(material)

        await self.session.commit()
        await self.session.refresh(material)

        return material

    async def update(
        self,
        material_id: int,
        data: MaterialUpdate,
    ) -> Material | None:
        material = await self.get_by_id(material_id)
        if material is None:
            return None

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(material, field, value)

        await self.session.commit()
        await self.session.refresh(material)

        return material

    async def delete(self, material_id: int) -> Material | None:
        material = await self.get_by_id(material_id)
        if material is None:
            return None

        await self.session.delete(material)
        await self.session.commit()

        return material
