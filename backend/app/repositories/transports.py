from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Transport
from app.schemas import TransportCreate, TransportUpdate


class TransportRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(
        self,
        transport_id: int,
    ) -> Transport | None:
        statement = select(Transport).where(Transport.id == transport_id)
        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def list_by_profile(
        self,
        profile_id: int,
    ) -> list[Transport]:
        statement = (
            select(Transport)
            .where(Transport.profile_id == profile_id)
            .order_by(Transport.id)
        )
        result = await self.session.execute(statement)

        return list(result.scalars().all())

    async def create(
        self,
        profile_id: int,
        data: TransportCreate,
    ) -> Transport:
        transport = Transport(
            profile_id=profile_id,
            **data.model_dump(),
        )
        self.session.add(transport)

        await self.session.commit()
        await self.session.refresh(transport)

        return transport

    async def update(
        self,
        transport_id: int,
        data: TransportUpdate,
    ) -> Transport | None:
        transport = await self.get_by_id(transport_id)
        if transport is None:
            return None

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(transport, field, value)

        await self.session.commit()
        await self.session.refresh(transport)

        return transport

    async def delete(
        self,
        transport_id: int,
    ) -> Transport | None:
        transport = await self.get_by_id(transport_id)
        if transport is None:
            return None

        await self.session.delete(transport)
        await self.session.commit()

        return transport
