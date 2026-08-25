from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.db import dependencies as db_dependencies
from app.db.database import Base
from app.db.dependencies import get_session
from app.main import app
from app.models import (
    CompanySize,
    CraneType,
    EnterpriseProfile,
    EquipmentType,
    MaterialForm,
    MaterialGroup,
    ProductionFacility,
    Region,
    TransportOwnershipType,
    TransportScope,
    TransportType,
    Warehouse,
    WarehouseType,
)

TEST_DATABASE_URL = "sqlite+aiosqlite://"

def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    event.listen(engine.sync_engine, "connect", _enable_sqlite_foreign_keys)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    try:
        async with session_factory() as session:
            yield session
    finally:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        await engine.dispose()


@pytest.fixture
async def reference_rows(db_session: AsyncSession) -> dict[str, str]:
    rows = [
        CompanySize(
            code="PNC_SIZE_SMALL",
            name_ru="Малое предприятие",
            ics_section="03.100.01",
            ref_system="World Bank / SME",
            ref_code="Small",
            description="Test fixture for a documented PNC value.",
        ),
        Region(
            code="PNC_REG_66",
            name_ru="Свердловская область",
            ics_section="03.100.10",
            ref_system="ISO 3166-2",
            ref_code="RU-SVE",
            description="Test fixture for a documented PNC value.",
        ),
        EquipmentType(
            code="TURNING",
            name_ru="Токарное оборудование",
            ics_section="25.080.10",
            ref_system="eCl@ss",
            ref_code="22-03-01-01",
            description="Test fixture for a documented PNC value.",
        ),
        EquipmentType(
            code="MILLING",
            name_ru="Фрезерное оборудование",
            ics_section="25.080.20",
            ref_system="eCl@ss",
            ref_code="22-03-01-02",
            description="Test fixture for a documented PNC value.",
        ),
        MaterialGroup(
            code="STEEL_CARBON",
            name_ru="Углеродистые и низколегированные стали",
            ics_section="77.140.01",
            ref_system="eCl@ss",
            ref_code="23-01-01-01",
            description="Test fixture for a documented PNC value.",
        ),
        MaterialGroup(
            code="STEEL_ALLOY",
            name_ru="Легированные и инструментальные стали",
            ics_section="77.140.20",
            ref_system="eCl@ss",
            ref_code="23-01-01-02",
            description="Test fixture for a documented PNC value.",
        ),
        MaterialForm(
            code="BAR_ROUND",
            name_ru="Круглый пруток",
            ics_section="77.140.60",
            ref_system="eCl@ss",
            ref_code="23-01-01-11",
            description="Test fixture for a documented PNC value.",
        ),
        CraneType(
            code="OVERHEAD_CRANE",
            name_ru="Мостовой кран",
            ics_section="53.020.20",
            ref_system="eCl@ss",
            ref_code="22-51-01-01",
            description="Test fixture for a documented PNC value.",
        ),
        CraneType(
            code="GANTRY_CRANE",
            name_ru="Козловой кран",
            ics_section="53.020.20",
            ref_system="eCl@ss",
            ref_code="22-51-01-02",
            description="Test fixture for a documented PNC value.",
        ),
        WarehouseType(
            code="UNIVERSAL",
            name_ru="Универсальный склад",
            ics_section="53.080.00",
            ref_system="eCl@ss",
            ref_code="41-01-01-00",
            description="Test fixture for a documented PNC value.",
        ),
        WarehouseType(
            code="FINISHED_GOODS",
            name_ru="Склад готовой продукции",
            ics_section="53.080.00",
            ref_system="eCl@ss",
            ref_code="41-01-01-02",
            description="Test fixture for a documented PNC value.",
        ),
        TransportType(
            code="LIGHT_COMMERCIAL",
            name_ru="Малотоннажный коммерческий транспорт",
            ics_section="43.080.10",
            ref_system="eCl@ss",
            ref_code="41-02-01-01",
            description="Test fixture for a documented PNC value.",
        ),
        TransportType(
            code="HEAVY_TRUCK",
            name_ru="Крупнотоннажный транспорт (Фуры)",
            ics_section="43.080.10",
            ref_system="eCl@ss",
            ref_code="41-02-01-02",
            description="Test fixture for a documented PNC value.",
        ),
        TransportScope(
            code="REGIONAL",
            name_ru="По региону",
            ics_section="03.100.10",
            ref_system="eCl@ss",
            ref_code="41-02-01-00",
            description="Test fixture for a documented PNC value.",
        ),
        TransportScope(
            code="NATIONAL",
            name_ru="По России (Национальный)",
            ics_section="03.100.10",
            ref_system="eCl@ss",
            ref_code="41-02-02-00",
            description="Test fixture for a documented PNC value.",
        ),
        TransportOwnershipType(
            code="PNC_OWN_OWNED",
            name_ru="Собственный транспорт",
            ics_section="03.100.10",
            ref_system="ISO / LogRef",
            ref_code="OWN",
            description="Test fixture for a documented PNC value.",
        ),
        TransportOwnershipType(
            code="PNC_OWN_LEASED",
            name_ru="Финансовый/оперативный лизинг",
            ics_section="03.100.10",
            ref_system="ISO / LogRef",
            ref_code="LEA",
            description="Test fixture for a documented PNC value.",
        ),
    ]
    db_session.add_all(rows)
    await db_session.commit()

    return {
        "company_size": "PNC_SIZE_SMALL",
        "region": "PNC_REG_66",
        "equipment_type": "TURNING",
        "other_equipment_type": "MILLING",
        "material_group": "STEEL_CARBON",
        "other_material_group": "STEEL_ALLOY",
        "material_form": "BAR_ROUND",
        "crane_type": "OVERHEAD_CRANE",
        "other_crane_type": "GANTRY_CRANE",
        "warehouse_type": "UNIVERSAL",
        "other_warehouse_type": "FINISHED_GOODS",
        "transport_type": "LIGHT_COMMERCIAL",
        "other_transport_type": "HEAVY_TRUCK",
        "transport_scope": "REGIONAL",
        "other_transport_scope": "NATIONAL",
        "transport_ownership_type": "PNC_OWN_OWNED",
        "other_transport_ownership_type": "PNC_OWN_LEASED",
    }


@pytest.fixture
async def enterprise_row(
    db_session: AsyncSession,
    reference_rows: dict[str, str],
) -> EnterpriseProfile:
    profile = EnterpriseProfile(
        company_name="Test enterprise",
        inn="6671000000",
        ogrn="1069600000000",
        website="https://example.test",
        employees_count=25,
        company_size_code=reference_rows["company_size"],
        region_code=reference_rows["region"],
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)
    return profile


@pytest.fixture
async def facility_row(
    db_session: AsyncSession,
    enterprise_row: EnterpriseProfile,
) -> ProductionFacility:
    facility = ProductionFacility(
        profile_id=enterprise_row.id,
        facility_name="Test facility",
        total_area=200.0,
        available_area=80.0,
        power_capacity=120.0,
        gas_supply=False,
        compressed_air=True,
        water_supply=True,
        steam_supply=False,
    )
    db_session.add(facility)
    await db_session.commit()
    await db_session.refresh(facility)
    return facility


@pytest.fixture
async def warehouse_row(
    db_session: AsyncSession,
    enterprise_row: EnterpriseProfile,
    reference_rows: dict[str, str],
) -> Warehouse:
    warehouse = Warehouse(
        profile_id=enterprise_row.id,
        warehouse_type_code=reference_rows["warehouse_type"],
        total_capacity_cube=120.0,
        max_load_sqm=15.0,
        temperature_control=False,
    )
    db_session.add(warehouse)
    await db_session.commit()
    await db_session.refresh(warehouse)
    return warehouse


@pytest.fixture
async def api_client(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[AsyncClient]:
    def blocked_production_session_factory(*_args, **_kwargs):
        raise AssertionError("Production AsyncSessionLocal must not be used in tests.")

    monkeypatch.setattr(
        db_dependencies,
        "AsyncSessionLocal",
        blocked_production_session_factory,
    )

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    original_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    try:
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)


@pytest.fixture
async def api_profile(
    api_client: AsyncClient,
    reference_rows: dict[str, str],
) -> dict[str, object]:
    response = await api_client.post(
        "/api/v1/enterprises",
        json={
            "company_name": "API test enterprise",
            "inn": "6671000001",
            "ogrn": "1069600000001",
            "website": "https://api.example.test",
            "employees_count": 30,
            "company_size_code": reference_rows["company_size"],
            "region_code": reference_rows["region"],
        },
    )
    assert response.status_code == 200
    return response.json()


@pytest.fixture
async def api_facility(
    api_client: AsyncClient,
    api_profile: dict[str, object],
) -> dict[str, object]:
    response = await api_client.post(
        f"/api/v1/enterprises/{api_profile['id']}/facilities",
        json={
            "facility_name": "API test facility",
            "total_area": 250.0,
            "available_area": 90.0,
            "power_capacity": 150.0,
            "gas_supply": False,
            "compressed_air": True,
            "water_supply": True,
            "steam_supply": False,
        },
    )
    assert response.status_code == 200
    return response.json()


@pytest.fixture
async def api_warehouse(
    api_client: AsyncClient,
    api_profile: dict[str, object],
    reference_rows: dict[str, str],
) -> dict[str, object]:
    response = await api_client.post(
        f"/api/v1/enterprises/{api_profile['id']}/warehouses",
        json={
            "warehouse_type_code": reference_rows["warehouse_type"],
            "total_capacity_cube": 120.0,
            "max_load_sqm": 15.0,
            "temperature_control": False,
        },
    )
    assert response.status_code == 200
    return response.json()
