import importlib.util
import re
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.models import (
    ProfileMaterialCapability,
    ProfileSectionCompleteness,
    ProfileTechnologyCapability,
)
from app.models.profile_capabilities import CONFIRMER_WHITESPACE_CODEPOINTS

FOUNDATION_MODELS = (
    ProfileTechnologyCapability,
    ProfileMaterialCapability,
    ProfileSectionCompleteness,
)

CONFIRMATION_CHECK_NAME = "ck_pnc_profile_section_completeness_confirmation"
# Canonical Python str.isspace() whitespace codepoint set.
FULLSET = set(CONFIRMER_WHITESPACE_CODEPOINTS)
PROBE_CODEPOINTS = (0x00A0, 0x2003, 0x202F)  # NBSP, EM SPACE, NARROW NBSP


def _normalize_sql(sql: str) -> str:
    normalized = re.sub(r"\s+", " ", sql).strip()
    return normalized.upper()


def extract_whitespace_codepoints(constraint_sql: str) -> set[int]:
    """Parse the trim(confirmed_by, <literal>) literal into a codepoint set.

    Supports both the PostgreSQL U&-escape form and the physical-character
    single-quoted form.
    """
    match = re.search(
        r"trim\s*\(\s*confirmed_by\s*,\s*(U&'[^']*'|'[^']*')",
        constraint_sql,
    )
    assert match is not None, f"No confirmer trim literal found in: {constraint_sql}"
    literal = match.group(1)
    if literal.startswith("U&"):
        escapes = literal[3:-1]
        codepoints: list[int] = []
        for i in range(0, len(escapes), 5):
            codepoints.append(int(escapes[i + 1 : i + 5], 16))
        return set(codepoints)
    inner = literal[1:-1]
    return {ord(ch) for ch in inner}


def load_migration_module():
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "c4a7f2d91e36_create_profile_capabilities_foundation.py"
    )
    spec = importlib.util.spec_from_file_location(
        "profile_capabilities_foundation_migration",
        migration_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def create_migrated_engine(
    existing_profile_ids: tuple[int, ...] = (),
) -> sa.Engine:
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    profiles = sa.Table(
        "pnc_enterprise_profile",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
    )
    sa.Table(
        "pnc_technology_type",
        metadata,
        sa.Column("code", sa.String(50), primary_key=True),
    )
    groups = sa.Table(
        "pnc_material_group",
        metadata,
        sa.Column("code", sa.String(50), primary_key=True),
    )
    sa.Table(
        "pnc_material",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_code", sa.ForeignKey(groups.c.code), nullable=False),
    )
    metadata.create_all(engine)

    migration = load_migration_module()
    with engine.begin() as connection:
        if existing_profile_ids:
            connection.execute(
                profiles.insert(),
                [{"id": profile_id} for profile_id in existing_profile_ids],
            )
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
    return engine


def test_foundation_migration_backfills_unknown_sections_without_revisions() -> None:
    engine = create_migrated_engine((1, 2))
    with engine.connect() as connection:
        rows = connection.execute(
            sa.text(
                "SELECT profile_id, section_code, state, confirmed_at, confirmed_by "
                "FROM pnc_profile_section_completeness "
                "ORDER BY profile_id, section_code"
            )
        ).all()

    assert rows == [
        (1, "MATERIALS", "UNKNOWN", None, None),
        (1, "TECHNOLOGIES", "UNKNOWN", None, None),
        (2, "MATERIALS", "UNKNOWN", None, None),
        (2, "TECHNOLOGIES", "UNKNOWN", None, None),
    ]
    inspector = sa.inspect(engine)
    assert {
        "pnc_profile_technology_capability",
        "pnc_profile_material_capability",
        "pnc_profile_section_completeness",
    }.issubset(inspector.get_table_names())
    section_columns = {
        column["name"]
        for column in inspector.get_columns("pnc_profile_section_completeness")
    }
    assert section_columns == {
        "profile_id",
        "section_code",
        "state",
        "confirmed_at",
        "confirmed_by",
    }


def test_foundation_migration_structure_matches_orm_metadata() -> None:
    engine = create_migrated_engine()
    inspector = sa.inspect(engine)

    for model in FOUNDATION_MODELS:
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
        migrated_primary_key = inspector.get_pk_constraint(table.name)
        assert tuple(migrated_primary_key["constrained_columns"]) == tuple(
            column.name for column in table.primary_key.columns
        )

        migrated_unique_names = {
            item["name"] for item in inspector.get_unique_constraints(table.name)
        }
        orm_unique_names = {
            constraint.name
            for constraint in table.constraints
            if isinstance(constraint, sa.UniqueConstraint)
        }
        assert migrated_unique_names == orm_unique_names

        migrated_check_names = {
            item["name"] for item in inspector.get_check_constraints(table.name)
        }
        orm_check_names = {
            constraint.name
            for constraint in table.constraints
            if isinstance(constraint, sa.CheckConstraint)
        }
        assert migrated_check_names == orm_check_names

        migrated_index_names = {
            item["name"] for item in inspector.get_indexes(table.name)
        }
        assert migrated_index_names == {index.name for index in table.indexes}

        migrated_foreign_keys = {
            (
                tuple(item["constrained_columns"]),
                item["referred_table"],
                tuple(item["referred_columns"]),
                item["options"].get("ondelete"),
            )
            for item in inspector.get_foreign_keys(table.name)
        }
        orm_foreign_keys = {
            (
                tuple(element.parent.name for element in constraint.elements),
                constraint.referred_table.name,
                tuple(element.column.name for element in constraint.elements),
                constraint.ondelete,
            )
            for constraint in table.foreign_key_constraints
        }
        assert migrated_foreign_keys == orm_foreign_keys


def test_foundation_migration_has_single_expected_parent() -> None:
    migration = load_migration_module()

    assert migration.revision == "c4a7f2d91e36"
    assert migration.down_revision == "b6a7d4e9c231"


def test_confirmation_check_whitespace_semantics_match_orm() -> None:
    engine = create_migrated_engine()
    inspector = sa.inspect(engine)

    migrated_confirmation = next(
        item["sqltext"]
        for item in inspector.get_check_constraints(
            "pnc_profile_section_completeness"
        )
        if item["name"] == CONFIRMATION_CHECK_NAME
    )

    orm_confirmation = next(
        constraint.sqltext.text
        for constraint in ProfileSectionCompleteness.__table__.constraints
        if isinstance(constraint, sa.CheckConstraint)
        and constraint.name == CONFIRMATION_CHECK_NAME
    )

    # Common confirmer guard structure, excluding dialect-specific literal.
    def guard_without_literal(sql: str) -> str:
        return _normalize_sql(re.sub(r"U&'[^']*'|'[^']*'", "<WS>", sql))

    assert guard_without_literal(migrated_confirmation) == guard_without_literal(
        orm_confirmation
    )

    migrated_set = extract_whitespace_codepoints(migrated_confirmation)
    orm_set = extract_whitespace_codepoints(orm_confirmation)

    assert migrated_set == FULLSET, f"Migrated set mismatch: {migrated_set!r}"
    assert orm_set == FULLSET, f"ORM set mismatch: {orm_set!r}"
    assert migrated_set == orm_set

    for probe in PROBE_CODEPOINTS:
        assert probe in migrated_set
        assert probe in orm_set


def test_confirmation_check_uses_full_whitespace_set_in_orm() -> None:
    orm_confirmation = next(
        constraint.sqltext.text
        for constraint in ProfileSectionCompleteness.__table__.constraints
        if isinstance(constraint, sa.CheckConstraint)
        and constraint.name == CONFIRMATION_CHECK_NAME
    )
    orm_set = extract_whitespace_codepoints(orm_confirmation)
    assert orm_set == FULLSET


def test_confirmation_check_postgres_uses_unicode_safe_literal() -> None:
    """The migration's confirmer literal is dialect-aware and PG-safe.

    PostgreSQL must receive a U&-escaped literal with no physical control or
    newline characters; the old char(...)||char(...) construction is gone.
    """
    from sqlalchemy.dialects import postgresql, sqlite

    def configure(dialect):
        connection = sa.engine.mock.MockConnection(
            dialect, lambda *args, **kwargs: []
        )
        migration = load_migration_module()
        migration.op = Operations(MigrationContext.configure(connection))
        return migration

    pg_migration = configure(postgresql.dialect())
    pg_literal = pg_migration._confirmer_whitespace_literal()
    assert pg_literal.startswith("U&'")
    assert pg_literal.endswith("'")
    assert "\n" not in pg_literal
    assert "char(" not in pg_literal.lower()
    pg_set = extract_whitespace_codepoints(f"trim(confirmed_by, {pg_literal})")
    assert pg_set == FULLSET
    for probe in PROBE_CODEPOINTS:
        assert probe in pg_set

    sqlite_migration = configure(sqlite.dialect())
    sqlite_literal = sqlite_migration._confirmer_whitespace_literal()
    assert not sqlite_literal.startswith("U&")
    sqlite_set = extract_whitespace_codepoints(
        f"trim(confirmed_by, {sqlite_literal})"
    )
    assert sqlite_set == FULLSET
    assert sqlite_set == pg_set
