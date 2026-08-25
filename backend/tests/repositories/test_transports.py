from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EnterpriseProfile
from app.repositories.transports import TransportRepository
from app.schemas import TransportCreate, TransportUpdate


async def test_transport_repository_crud_preserves_patch_presence_semantics(
    db_session: AsyncSession,
    enterprise_row: EnterpriseProfile,
    reference_rows: dict[str, str],
) -> None:
    repository = TransportRepository(db_session)
    created = await repository.create(
        enterprise_row.id,
        TransportCreate(
            transport_type_code=reference_rows["transport_type"],
            transport_scope_code=reference_rows["transport_scope"],
            transport_ownership_code=reference_rows[
                "transport_ownership_type"
            ],
            payload_tons=1.5,
            body_volume_cube=12.0,
            has_refrigeration=True,
            quantity=2,
        ),
    )

    fetched = await repository.get_by_id(created.id)
    listed = await repository.list_by_profile(enterprise_row.id)

    assert fetched is not None
    assert [transport.id for transport in listed] == [created.id]

    false_state = await repository.update(
        created.id,
        TransportUpdate(
            payload_tons=2.0,
            has_refrigeration=False,
        ),
    )
    assert false_state is not None
    assert false_state.payload_tons == 2.0
    assert false_state.has_refrigeration is False
    assert false_state.body_volume_cube == 12.0

    cleared = await repository.update(
        created.id,
        TransportUpdate(
            body_volume_cube=None,
            has_refrigeration=None,
        ),
    )
    assert cleared is not None
    assert cleared.body_volume_cube is None
    assert cleared.has_refrigeration is None
    assert cleared.payload_tons == 2.0
    assert cleared.quantity == 2

    unchanged = await repository.update(created.id, TransportUpdate())
    assert unchanged is not None
    assert unchanged.body_volume_cube is None
    assert unchanged.has_refrigeration is None
    assert unchanged.payload_tons == 2.0
    assert unchanged.quantity == 2

    deleted = await repository.delete(created.id)

    assert deleted is not None
    assert await repository.get_by_id(created.id) is None


async def test_transport_repository_list_by_profile_excludes_other_profiles(
    db_session: AsyncSession,
    enterprise_row: EnterpriseProfile,
    reference_rows: dict[str, str],
) -> None:
    other_profile = EnterpriseProfile(company_name="Other transport profile")
    db_session.add(other_profile)
    await db_session.commit()
    await db_session.refresh(other_profile)

    repository = TransportRepository(db_session)
    create_data = TransportCreate(
        transport_type_code=reference_rows["transport_type"],
        transport_scope_code=reference_rows["transport_scope"],
        transport_ownership_code=reference_rows[
            "transport_ownership_type"
        ],
        payload_tons=1.5,
    )
    own_transport = await repository.create(enterprise_row.id, create_data)
    other_transport = await repository.create(other_profile.id, create_data)

    own_list = await repository.list_by_profile(enterprise_row.id)
    other_list = await repository.list_by_profile(other_profile.id)

    assert [transport.id for transport in own_list] == [own_transport.id]
    assert [transport.id for transport in other_list] == [other_transport.id]
