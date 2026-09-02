from app.core.exceptions import (
    DuplicateMaterialError,
    MaterialGroupNotFoundError,
    MaterialInUseError,
    MaterialNotFoundError,
    MaterialReclassificationBlockedError,
)
from app.models import Material
from app.repositories import MaterialRepository, ReferenceRepository
from app.schemas import MaterialCreate, MaterialUpdate


class MaterialService:
    def __init__(
        self,
        repository: MaterialRepository,
        reference_repository: ReferenceRepository,
    ):
        self.repository = repository
        self.reference_repository = reference_repository

    async def _validate_material_group(self, code: str) -> None:
        material_group = (
            await self.reference_repository.get_material_group_by_code(code)
        )
        if material_group is None:
            raise MaterialGroupNotFoundError(
                f"Material group {code} not found."
            )

    async def _validate_unique_grade(
        self,
        group_code: str,
        grade_name: str,
        material_id: int | None = None,
    ) -> None:
        existing = await self.repository.get_by_group_and_grade(
            group_code,
            grade_name,
        )
        if existing is not None and existing.id != material_id:
            raise DuplicateMaterialError(
                f"Material {group_code}/{grade_name} already exists."
            )

    async def get_material(self, material_id: int) -> Material:
        material = await self.repository.get_by_id(material_id)
        if material is None:
            raise MaterialNotFoundError(
                f"Material {material_id} not found."
            )

        return material

    async def list_materials(self) -> list[Material]:
        return await self.repository.list_materials()

    async def create_material(self, data: MaterialCreate) -> Material:
        await self._validate_material_group(data.group_code)
        await self._validate_unique_grade(data.group_code, data.grade_name)

        return await self.repository.create(data)

    async def update_material(
        self,
        material_id: int,
        data: MaterialUpdate,
    ) -> Material:
        material = await self.repository.get_by_id(material_id)
        if material is None:
            raise MaterialNotFoundError(
                f"Material {material_id} not found."
            )

        group_code = material.group_code
        grade_name = material.grade_name

        if (
            "group_code" in data.model_fields_set
            and data.group_code is not None
        ):
            group_code = data.group_code
            await self._validate_material_group(group_code)
        if (
            "grade_name" in data.model_fields_set
            and data.grade_name is not None
        ):
            grade_name = data.grade_name

        if {"group_code", "grade_name"} & data.model_fields_set:
            await self._validate_unique_grade(
                group_code,
                grade_name,
                material_id,
            )

        if (
            group_code != material.group_code
            and await self.repository.has_reclassification_capability_dependencies(
                material_id,
                material.group_code,
                group_code,
            )
        ):
            raise MaterialReclassificationBlockedError(
                f"Material {material_id} group cannot change while profile "
                "material capabilities depend on the material or affected groups."
            )

        updated = await self.repository.update(material_id, data)
        if updated is None:
            raise MaterialNotFoundError(
                f"Material {material_id} not found."
            )

        return updated

    async def delete_material(self, material_id: int) -> Material:
        material = await self.repository.get_by_id(material_id)
        if material is None:
            raise MaterialNotFoundError(
                f"Material {material_id} not found."
            )

        if await self.repository.has_material_items(material_id):
            raise MaterialInUseError(
                f"Material {material_id} is used by material items."
            )

        if await self.repository.has_profile_capabilities(material_id):
            raise MaterialInUseError(
                f"Material {material_id} is used by profile material capabilities."
            )

        deleted = await self.repository.delete(material_id)
        if deleted is None:
            raise MaterialNotFoundError(
                f"Material {material_id} not found."
            )

        return deleted
