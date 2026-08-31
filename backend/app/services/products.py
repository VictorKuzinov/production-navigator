from app.core.exceptions import (
    DuplicateProductError,
    EnterpriseProfileNotFoundError,
    MaterialItemNotFoundError,
    ProductInUseError,
    ProductNotFoundError,
    ProductTypeNotFoundError,
)
from app.models import Product
from app.repositories import (
    EnterpriseProfileRepository,
    MaterialItemRepository,
    ProductRepository,
    ReferenceRepository,
)
from app.schemas import ProductCreate, ProductUpdate


class ProductService:
    def __init__(
        self,
        repository: ProductRepository,
        enterprise_repository: EnterpriseProfileRepository,
        material_item_repository: MaterialItemRepository,
        reference_repository: ReferenceRepository,
    ):
        self.repository = repository
        self.enterprise_repository = enterprise_repository
        self.material_item_repository = material_item_repository
        self.reference_repository = reference_repository

    async def _validate_product_type(self, code: str) -> None:
        product_type = await self.reference_repository.get_product_type_by_code(code)
        if product_type is None:
            raise ProductTypeNotFoundError(f"Product type {code} not found.")

    async def _validate_material_item(self, material_item_id: int) -> None:
        material_item = await self.material_item_repository.get_by_id(
            material_item_id
        )
        if material_item is None:
            raise MaterialItemNotFoundError(
                f"Material item {material_item_id} not found."
            )

    async def _validate_unique_sku(
        self,
        profile_id: int,
        sku_code: str,
        product_id: int | None = None,
    ) -> None:
        existing = await self.repository.get_by_profile_sku(
            profile_id,
            sku_code,
        )
        if existing is not None and existing.id != product_id:
            raise DuplicateProductError(
                f"Product {profile_id}/{sku_code} already exists."
            )

    async def get_product(self, product_id: int) -> Product:
        product = await self.repository.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundError(f"Product {product_id} not found.")

        return product

    async def list_products(self, profile_id: int) -> list[Product]:
        profile = await self.enterprise_repository.get_by_id(profile_id)
        if profile is None:
            raise EnterpriseProfileNotFoundError(
                f"Enterprise profile {profile_id} not found."
            )

        return await self.repository.list_by_profile(profile_id)

    async def create_product(
        self,
        profile_id: int,
        data: ProductCreate,
    ) -> Product:
        profile = await self.enterprise_repository.get_by_id(profile_id)
        if profile is None:
            raise EnterpriseProfileNotFoundError(
                f"Enterprise profile {profile_id} not found."
            )

        await self._validate_product_type(data.product_type_code)
        await self._validate_material_item(data.material_item_id)
        await self._validate_unique_sku(profile_id, data.sku_code)

        return await self.repository.create(profile_id, data)

    async def update_product(
        self,
        product_id: int,
        data: ProductUpdate,
    ) -> Product:
        product = await self.repository.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundError(f"Product {product_id} not found.")

        fields = data.model_fields_set
        if fields and await self.repository.has_orders(product_id):
            raise ProductInUseError(
                f"Product {product_id} is used by production orders "
                "and cannot be changed."
            )

        if (
            "product_type_code" in fields
            and data.product_type_code is not None
        ):
            await self._validate_product_type(data.product_type_code)
        if "material_item_id" in fields and data.material_item_id is not None:
            await self._validate_material_item(data.material_item_id)
        if "sku_code" in fields and data.sku_code is not None:
            await self._validate_unique_sku(
                product.profile_id,
                data.sku_code,
                product_id,
            )

        updated = await self.repository.update(product_id, data)
        if updated is None:
            raise ProductNotFoundError(f"Product {product_id} not found.")

        return updated

    async def delete_product(self, product_id: int) -> Product:
        product = await self.repository.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundError(f"Product {product_id} not found.")

        if await self.repository.has_orders(product_id):
            raise ProductInUseError(
                f"Product {product_id} is used by production orders."
            )

        deleted = await self.repository.delete(product_id)
        if deleted is None:
            raise ProductNotFoundError(f"Product {product_id} not found.")

        return deleted
