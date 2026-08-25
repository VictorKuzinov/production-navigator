from app.core.exceptions import (
    EnterpriseProfileNotFoundError,
    TransportNotFoundError,
    TransportOwnershipTypeNotFoundError,
    TransportScopeNotFoundError,
    TransportTypeNotFoundError,
)
from app.models import Transport
from app.repositories import (
    EnterpriseProfileRepository,
    ReferenceRepository,
    TransportRepository,
)
from app.schemas import TransportCreate, TransportUpdate


class TransportService:
    def __init__(
        self,
        repository: TransportRepository,
        enterprise_repository: EnterpriseProfileRepository,
        reference_repository: ReferenceRepository,
    ):
        self.repository = repository
        self.enterprise_repository = enterprise_repository
        self.reference_repository = reference_repository

    async def _validate_transport_type(self, code: str) -> None:
        transport_type = (
            await self.reference_repository.get_transport_type_by_code(code)
        )
        if transport_type is None:
            raise TransportTypeNotFoundError(
                f"Transport type {code} not found."
            )

    async def _validate_transport_scope(self, code: str) -> None:
        transport_scope = (
            await self.reference_repository.get_transport_scope_by_code(code)
        )
        if transport_scope is None:
            raise TransportScopeNotFoundError(
                f"Transport scope {code} not found."
            )

    async def _validate_transport_ownership_type(self, code: str) -> None:
        transport_ownership_type = await (
            self.reference_repository.get_transport_ownership_type_by_code(code)
        )
        if transport_ownership_type is None:
            raise TransportOwnershipTypeNotFoundError(
                f"Transport ownership type {code} not found."
            )

    async def get_transport(
        self,
        transport_id: int,
    ) -> Transport:
        transport = await self.repository.get_by_id(transport_id)
        if transport is None:
            raise TransportNotFoundError(
                f"Transport {transport_id} not found."
            )

        return transport

    async def list_transports(
        self,
        profile_id: int,
    ) -> list[Transport]:
        profile = await self.enterprise_repository.get_by_id(profile_id)
        if profile is None:
            raise EnterpriseProfileNotFoundError(
                f"Enterprise profile {profile_id} not found."
            )

        return await self.repository.list_by_profile(profile_id)

    async def create_transport(
        self,
        profile_id: int,
        data: TransportCreate,
    ) -> Transport:
        profile = await self.enterprise_repository.get_by_id(profile_id)
        if profile is None:
            raise EnterpriseProfileNotFoundError(
                f"Enterprise profile {profile_id} not found."
            )

        await self._validate_transport_type(data.transport_type_code)
        await self._validate_transport_scope(data.transport_scope_code)
        await self._validate_transport_ownership_type(
            data.transport_ownership_code
        )

        return await self.repository.create(profile_id, data)

    async def update_transport(
        self,
        transport_id: int,
        data: TransportUpdate,
    ) -> Transport:
        transport = await self.repository.get_by_id(transport_id)
        if transport is None:
            raise TransportNotFoundError(
                f"Transport {transport_id} not found."
            )

        if (
            "transport_type_code" in data.model_fields_set
            and data.transport_type_code is not None
        ):
            await self._validate_transport_type(data.transport_type_code)
        if (
            "transport_scope_code" in data.model_fields_set
            and data.transport_scope_code is not None
        ):
            await self._validate_transport_scope(data.transport_scope_code)
        if (
            "transport_ownership_code" in data.model_fields_set
            and data.transport_ownership_code is not None
        ):
            await self._validate_transport_ownership_type(
                data.transport_ownership_code
            )

        updated = await self.repository.update(transport_id, data)
        if updated is None:
            raise TransportNotFoundError(
                f"Transport {transport_id} not found."
            )

        return updated

    async def delete_transport(
        self,
        transport_id: int,
    ) -> Transport:
        transport = await self.repository.get_by_id(transport_id)
        if transport is None:
            raise TransportNotFoundError(
                f"Transport {transport_id} not found."
            )

        deleted = await self.repository.delete(transport_id)
        if deleted is None:
            raise TransportNotFoundError(
                f"Transport {transport_id} not found."
            )

        return deleted
