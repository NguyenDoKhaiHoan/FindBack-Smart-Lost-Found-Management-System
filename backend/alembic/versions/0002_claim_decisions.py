"""Return confirmation actor and unambiguous Post completion metadata.

Revision ID: 0002_claim_decisions
Revises: 0001_claims_api
"""

import sqlalchemy as sa

from alembic import op

revision = "0002_claim_decisions"
down_revision = "0001_claims_api"
branch_labels = None
depends_on = None


def upgrade(schema=None):
    with op.batch_alter_table("posts", schema=schema) as batch:
        batch.add_column(sa.Column("completed_claim_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_foreign_key(
            "fk_post_completed_claim",
            "claims",
            ["completed_claim_id"],
            ["id"],
            referent_schema=schema,
        )
        batch.create_check_constraint(
            "ck_post_completion",
            "(completed_claim_id IS NULL AND completed_at IS NULL) OR "
            "(status = 'CLOSED' AND completed_claim_id IS NOT NULL AND completed_at IS NOT NULL)",
        )
    with op.batch_alter_table("returns", schema=schema) as batch:
        batch.add_column(sa.Column("confirmed_by", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_return_confirmed_by",
            "users",
            ["confirmed_by"],
            ["id"],
            referent_schema=schema,
        )
        # Existing legacy rows are retained; only new confirmations populate this actor.
        batch.create_check_constraint(
            "ck_return_confirmation_actor",
            "confirmed_by IS NULL OR (status = 'CONFIRMED' AND confirmed_at IS NOT NULL)",
        )


def downgrade(schema=None):
    with op.batch_alter_table("returns", schema=schema) as batch:
        batch.drop_constraint("ck_return_confirmation_actor", type_="check")
        batch.drop_constraint("fk_return_confirmed_by", type_="foreignkey")
        batch.drop_column("confirmed_by")
    with op.batch_alter_table("posts", schema=schema) as batch:
        batch.drop_constraint("ck_post_completion", type_="check")
        batch.drop_constraint("fk_post_completed_claim", type_="foreignkey")
        batch.drop_column("completed_at")
        batch.drop_column("completed_claim_id")
