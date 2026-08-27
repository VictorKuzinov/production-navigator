from math import isfinite

from app.core.exceptions import (
    DuplicateMaterialItemError,
    InvalidMaterialItemError,
    MaterialFormNotFoundError,
    MaterialItemInUseError,
    MaterialItemNotFoundError,
    MaterialNotFoundError,
)
from app.models import MaterialItem
from app.repositories import (
    MaterialItemRepository,
    MaterialRepository,
    ReferenceRepository,
)
from app.schemas import MaterialItemCreate, MaterialItemUpdate


class MaterialItemService:
    def __init__(
        self,
        repository: MaterialItemRepository,
        material_repository: MaterialRepository,
        reference_repository: ReferenceRepository,
    ):
        self.repository = repository
        self.material_repository = material_repository
        self.reference_repository = reference_repository

    async def _validate_material(self, material_id: int) -> None:
        material = await self.material_repository.get_by_id(material_id)
        if material is None:
            raise MaterialNotFoundError(f"Material {material_id} not found.")

    async def _validate_material_form(self, code: str) -> None:
        material_form = await self.reference_repository.get_material_form_by_code(code)
        if material_form is None:
            raise MaterialFormNotFoundError(f"Material form {code} not found.")

    def _validate_dimension(
        self,
        material_form_code: str,
        dimension_1: float | None,
    ) -> None:
        if dimension_1 is not None and (not isfinite(dimension_1) or dimension_1 <= 0):
            raise InvalidMaterialItemError(
                "dimension_1 must be finite and greater than zero."
            )
        if material_form_code == "LIQUID_CHEMICAL" and dimension_1 is not None:
            raise InvalidMaterialItemError(
                "dimension_1 must be null for LIQUID_CHEMICAL."
            )

    async def _validate_unique_identity(
        self,
        material_id: int,
        material_form_code: str,
        dimension_1: float | None,
        unit_of_measure: str,
        material_item_id: int | None = None,
    ) -> None:
        existing = await self.repository.get_by_identity(
            material_id,
            material_form_code,
            dimension_1,
            unit_of_measure,
        )
        if existing is not None and existing.id != material_item_id:
            raise DuplicateMaterialItemError(
                "Material item with the same identity already exists."
            )

    async def get_material_item(
        self,
        material_item_id: int,
    ) -> MaterialItem:
        material_item = await self.repository.get_by_id(material_item_id)
        if material_item is None:
            raise MaterialItemNotFoundError(
                f"Material item {material_item_id} not found."
            )

        return material_item

    async def list_material_items(self) -> list[MaterialItem]:
        return await self.repository.list_material_items()

    async def create_material_item(
        self,
        data: MaterialItemCreate,
    ) -> MaterialItem:
        await self._validate_material(data.material_id)
        await self._validate_material_form(data.material_form_code)
        self._validate_dimension(data.material_form_code, data.dimension_1)
        await self._validate_unique_identity(
            data.material_id,
            data.material_form_code,
            data.dimension_1,
            data.unit_of_measure,
        )

        return await self.repository.create(data)

    async def update_material_item(
        self,
        material_item_id: int,
        data: MaterialItemUpdate,
    ) -> MaterialItem:
        material_item = await self.repository.get_by_id(material_item_id)
        if material_item is None:
            raise MaterialItemNotFoundError(
                f"Material item {material_item_id} not found."
            )

        fields = data.model_fields_set
        if fields and await self.repository.has_products(material_item_id):
            raise MaterialItemInUseError(
                f"Material item {material_item_id} is used by products "
                "and cannot be changed."
            )

        material_id = material_item.material_id
        material_form_code = material_item.material_form_code
        dimension_1 = material_item.dimension_1
        unit_of_measure = material_item.unit_of_measure

        if "material_id" in fields and data.material_id is not None:
            material_id = data.material_id
            await self._validate_material(material_id)
        if "material_form_code" in fields and data.material_form_code is not None:
            material_form_code = data.material_form_code
            await self._validate_material_form(material_form_code)
        if "dimension_1" in fields:
            dimension_1 = data.dimension_1
        if "unit_of_measure" in fields and data.unit_of_measure is not None:
            unit_of_measure = data.unit_of_measure

        self._validate_dimension(material_form_code, dimension_1)
        if fields:
            await self._validate_unique_identity(
                material_id,
                material_form_code,
                dimension_1,
                unit_of_measure,
                material_item_id,
            )

        updated = await self.repository.update(material_item_id, data)
        if updated is None:
            raise MaterialItemNotFoundError(
                f"Material item {material_item_id} not found."
            )

        return updated

    async def delete_material_item(
        self,
        material_item_id: int,
    ) -> MaterialItem:
        material_item = await self.repository.get_by_id(material_item_id)
        if material_item is None:
            raise MaterialItemNotFoundError(
                f"Material item {material_item_id} not found."
            )

        if await self.repository.has_products(material_item_id):
            raise MaterialItemInUseError(
                f"Material item {material_item_id} is used by products."
            )

        deleted = await self.repository.delete(material_item_id)
        if deleted is None:
            raise MaterialItemNotFoundError(
                f"Material item {material_item_id} not found."
            )

        return deleted
