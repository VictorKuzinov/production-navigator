import importlib.util
import io
import re
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from app.models import (
    ProcurementCertificateRequirement,
    ProcurementEquipmentRequirement,
    ProcurementMaterialRequirement,
    ProcurementOpportunity,
    ProcurementOpportunityProductType,
    ProcurementTechnologyRequirement,
)

REVISION = "d18a4f3c7b92"
PARENT_REVISION = "c4a7f2d91e36"
NEW_TABLES = {
    "pnc_procurement_opportunity",
    "pnc_procurement_opportunity_product_type",
    "pnc_procurement_material_requirement",
    "pnc_procurement_technology_requirement",
    "pnc_procurement_equipment_requirement",
    "pnc_procurement_certificate_requirement",
}
MODELS = (
    ProcurementOpportunity,
    ProcurementOpportunityProductType,
    ProcurementMaterialRequirement,
    ProcurementTechnologyRequirement,
    ProcurementEquipmentRequirement,
    ProcurementCertificateRequirement,
)


def load_migration_module():
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / f"{REVISION}_create_procurement_opportunity_ingestion.py"
    )
    spec = importlib.util.spec_from_file_location(
        "procurement_opportunity_ingestion_migration",
        migration_path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reference_metadata() -> sa.MetaData:
    metadata = sa.MetaData()
    for table_name in (
        "pnc_region",
        "pnc_product_type",
        "pnc_material_group",
        "pnc_technology_type",
        "pnc_equipment_type",
        "pnc_certificate_type",
    ):
        sa.Table(
            table_name,
            metadata,
            sa.Column("code", sa.String(50), primary_key=True),
        )
    sa.Table(
        "pnc_material",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_code", sa.String(50), nullable=False),
    )
    return metadata


def create_migrated_engine() -> sa.Engine:
    engine = sa.create_engine("sqlite://")
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    reference_metadata().create_all(engine)
    migration = load_migration_module()
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
    return engine


def normalize_sql(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().upper()


def test_migration_is_single_child_and_alembic_has_one_head_without_branches() -> None:
    migration = load_migration_module()
    assert migration.revision == REVISION
    assert migration.down_revision == PARENT_REVISION

    backend = Path(__file__).parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == [REVISION]
    assert [
        revision.revision
        for revision in script.walk_revisions()
        if len(revision.nextrev) > 1
    ] == []


def test_migration_creates_exactly_six_new_tables_and_matches_orm() -> None:
    engine = create_migrated_engine()
    inspector = sa.inspect(engine)
    all_tables = set(inspector.get_table_names())
    assert NEW_TABLES.issubset(all_tables)
    assert all_tables - set(reference_metadata().tables) == NEW_TABLES

    for model in MODELS:
        table = model.__table__
        migrated_columns = {
            column["name"]: (str(column["type"]).upper(), column["nullable"])
            for column in inspector.get_columns(table.name)
        }
        orm_columns = {
            column.name: (str(column.type).upper(), column.nullable)
            for column in table.columns
        }
        assert migrated_columns == orm_columns
        assert tuple(
            inspector.get_pk_constraint(table.name)["constrained_columns"]
        ) == (tuple(column.name for column in table.primary_key.columns))

        migrated_uniques = {
            item["name"] for item in inspector.get_unique_constraints(table.name)
        }
        orm_uniques = {
            constraint.name
            for constraint in table.constraints
            if isinstance(constraint, sa.UniqueConstraint)
        }
        assert migrated_uniques == orm_uniques

        migrated_checks = {
            item["name"]: normalize_sql(item["sqltext"])
            for item in inspector.get_check_constraints(table.name)
        }
        orm_checks = {
            constraint.name: normalize_sql(str(constraint.sqltext))
            for constraint in table.constraints
            if isinstance(constraint, sa.CheckConstraint)
        }
        assert migrated_checks == orm_checks

        assert {item["name"] for item in inspector.get_indexes(table.name)} == {
            index.name for index in table.indexes
        }
        migrated_fks = {
            (
                tuple(item["constrained_columns"]),
                item["referred_table"],
                tuple(item["referred_columns"]),
                item["options"].get("ondelete"),
            )
            for item in inspector.get_foreign_keys(table.name)
        }
        orm_fks = {
            (
                tuple(element.parent.name for element in constraint.elements),
                constraint.referred_table.name,
                tuple(element.column.name for element in constraint.elements),
                constraint.ondelete,
            )
            for constraint in table.foreign_key_constraints
        }
        assert migrated_fks == orm_fks


def test_material_partial_indexes_execute_in_sqlite() -> None:
    engine = create_migrated_engine()
    with engine.begin() as connection:
        connection.execute(
            sa.text("INSERT INTO pnc_material_group (code) VALUES ('STEEL_CARBON')")
        )
        connection.execute(
            sa.text(
                "INSERT INTO pnc_procurement_opportunity "
                "(id, source, external_id, title, status, "
                "product_type_codes_state, material_requirements_state, "
                "technology_requirements_state, equipment_requirements_state, "
                "required_certificates_state) VALUES "
                "(1, 'fixture', 'one', 'One', 'OPEN', "
                "'UNKNOWN', 'KNOWN', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN')"
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO pnc_procurement_material_requirement "
                "(opportunity_id, material_group_code, material_id, "
                "requirement_strength) VALUES "
                "(1, 'STEEL_CARBON', NULL, 'MANDATORY')"
            )
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                sa.text(
                    "INSERT INTO pnc_procurement_material_requirement "
                    "(opportunity_id, material_group_code, material_id, "
                    "requirement_strength) VALUES "
                    "(1, 'STEEL_CARBON', NULL, 'PREFERRED')"
                )
            )


def test_postgresql_offline_upgrade_and_downgrade_render_generic_json() -> None:
    output = io.StringIO()
    context = MigrationContext.configure(
        url="postgresql://",
        opts={"as_sql": True, "output_buffer": output},
    )
    migration = load_migration_module()
    migration.op = Operations(context)
    migration.upgrade()
    migration.downgrade()
    sql = output.getvalue()

    assert "CREATE TABLE pnc_procurement_opportunity" in sql
    assert "JSONB" not in sql
    assert " JSON" in sql
    assert "WHERE material_id IS NULL" in sql
    assert "WHERE material_id IS NOT NULL" in sql
    assert "DROP TABLE pnc_procurement_opportunity" in sql


def test_downgrade_removes_only_six_new_tables() -> None:
    engine = create_migrated_engine()
    migration = load_migration_module()
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.downgrade()

    remaining = set(sa.inspect(engine).get_table_names())
    assert NEW_TABLES.isdisjoint(remaining)
    assert remaining == set(reference_metadata().tables)
