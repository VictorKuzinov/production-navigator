"""enforce MaterialItem nullable uniqueness

Revision ID: b6a7d4e9c231
Revises: 27a920326238
Create Date: 2026-08-26 16:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b6a7d4e9c231"
down_revision: str | Sequence[str] | None = "27a920326238"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM pnc_material_item
                    GROUP BY
                        material_id,
                        material_form_code,
                        dimension_1,
                        unit_of_measure
                    HAVING COUNT(*) > 1
                ) THEN
                    RAISE EXCEPTION
                        'MaterialItem duplicates require explicit data mapping';
                END IF;
            END
            $$
            """
        )
    )
    op.drop_constraint(
        "uq_pnc_material_item_form_dimension_unit",
        "pnc_material_item",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_pnc_material_item_form_dimension_unit",
        "pnc_material_item",
        [
            "material_id",
            "material_form_code",
            "dimension_1",
            "unit_of_measure",
        ],
        postgresql_nulls_not_distinct=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "uq_pnc_material_item_form_dimension_unit",
        "pnc_material_item",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_pnc_material_item_form_dimension_unit",
        "pnc_material_item",
        [
            "material_id",
            "material_form_code",
            "dimension_1",
            "unit_of_measure",
        ],
    )
