from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Product, ProductionOrder
from app.schemas import ProductCreate, ProductUpdate


class ProductRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(
        self,
        product_id: int,
    ) -> Product | None:
        statement = select(Product).where(Product.id == product_id)
        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def get_by_profile_sku(
        self,
        profile_id: int,
        sku_code: str,
    ) -> Product | None:
        statement = select(Product).where(
            Product.profile_id == profile_id,
            Product.sku_code == sku_code,
        )
        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def list_by_profile(
        self,
        profile_id: int,
    ) -> list[Product]:
        statement = (
            select(Product)
            .where(Product.profile_id == profile_id)
            .order_by(Product.id)
        )
        result = await self.session.execute(statement)

        return list(result.scalars().all())

    async def has_orders(self, product_id: int) -> bool:
        statement = (
            select(ProductionOrder.id)
            .where(ProductionOrder.product_id == product_id)
            .limit(1)
        )
        result = await self.session.execute(statement)

        return result.scalar_one_or_none() is not None

    async def create(
        self,
        profile_id: int,
        data: ProductCreate,
    ) -> Product:
        product = Product(
            profile_id=profile_id,
            **data.model_dump(),
        )
        self.session.add(product)

        await self.session.commit()
        await self.session.refresh(product)

        return product

    async def update(
        self,
        product_id: int,
        data: ProductUpdate,
    ) -> Product | None:
        product = await self.get_by_id(product_id)
        if product is None:
            return None

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(product, field, value)

        await self.session.commit()
        await self.session.refresh(product)

        return product

    async def delete(
        self,
        product_id: int,
    ) -> Product | None:
        product = await self.get_by_id(product_id)
        if product is None:
            return None

        await self.session.delete(product)
        await self.session.commit()

        return product
