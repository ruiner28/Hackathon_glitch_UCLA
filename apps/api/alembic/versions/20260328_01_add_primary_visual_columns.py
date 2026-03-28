"""Add primary visual columns and scene enum value.

Revision ID: 20260328_01
Revises:
Create Date: 2026-03-28
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260328_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    with op.batch_alter_table("lesson_plans") as batch_op:
        batch_op.add_column(sa.Column("diagram_spec_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("walkthrough_states_json", sa.JSON(), nullable=True))

    # Add the new enum variant used by diagram walkthrough scenes.
    if dialect_name == "postgresql":
        op.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_type t
                    JOIN pg_enum e ON t.oid = e.enumtypid
                    WHERE t.typname = 'scenetype'
                      AND e.enumlabel = 'primary_visual_walkthrough'
                ) THEN
                    ALTER TYPE scenetype ADD VALUE 'primary_visual_walkthrough';
                END IF;
            END$$;
            """
        )


def downgrade() -> None:
    with op.batch_alter_table("lesson_plans") as batch_op:
        batch_op.drop_column("walkthrough_states_json")
        batch_op.drop_column("diagram_spec_json")
    # PostgreSQL enum value removal is intentionally omitted (not safely reversible).
