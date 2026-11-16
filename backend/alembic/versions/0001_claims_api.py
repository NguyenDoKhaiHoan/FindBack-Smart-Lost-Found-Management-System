"""Isolated UUID-based Claims API persistence and minimal Identity/Posts adapters.

Revision ID: 0001_claims_api
Revises: none
"""

import sqlalchemy as sa

from alembic import op

revision = "0001_claims_api"
down_revision = None
branch_labels = None
depends_on = None


def upgrade(schema=None):
    def fk(table):
        return f"{schema}.{table}.id" if schema else f"{table}.id"

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.CheckConstraint("token_version >= 1", name="ck_user_token_version"),
        schema=schema,
    )
    op.create_table(
        "revoked_tokens",
        sa.Column("jti", sa.String(128), primary_key=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        schema=schema,
    )
    op.create_table(
        "posts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey(fk("users")), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("is_hidden", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("type IN ('FOUND', 'LOST')", name="ck_post_type"),
        sa.CheckConstraint("status IN ('OPEN', 'CLOSED')", name="ck_post_status"),
        schema=schema,
    )
    op.create_index("ix_posts_owner_id", "posts", ["owner_id"], schema=schema)
    op.create_table(
        "claims",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("found_post_id", sa.Uuid(), sa.ForeignKey(fk("posts")), nullable=False),
        sa.Column("claimant_id", sa.Uuid(), sa.ForeignKey(fk("users")), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by", sa.Uuid(), sa.ForeignKey(fk("users"))),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("rejection_reason", sa.Text()),
        sa.Column("returned_by", sa.Uuid(), sa.ForeignKey(fk("users"))),
        sa.Column("returned_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('PENDING','APPROVED','REJECTED','RETURNED')", name="ck_claim_status"
        ),
        sa.CheckConstraint("version >= 1", name="ck_claim_version"),
        sa.CheckConstraint(
            "(status = 'PENDING' AND decided_by IS NULL AND decided_at IS NULL) OR "
            "(status <> 'PENDING' AND decided_by IS NOT NULL AND decided_at IS NOT NULL)",
            name="ck_claim_decision",
        ),
        sa.CheckConstraint(
            "(status = 'REJECTED' AND rejection_reason IS NOT NULL "
            "AND length(trim(rejection_reason)) > 0) OR "
            "(status <> 'REJECTED' AND rejection_reason IS NULL)",
            name="ck_claim_rejection",
        ),
        sa.CheckConstraint(
            "(status = 'RETURNED' AND returned_by IS NOT NULL "
            "AND returned_by = claimant_id AND returned_at IS NOT NULL) OR "
            "(status <> 'RETURNED' AND returned_by IS NULL AND returned_at IS NULL)",
            name="ck_claim_return",
        ),
        schema=schema,
    )
    op.create_index("ix_claims_found_post_id", "claims", ["found_post_id"], schema=schema)
    op.create_index(
        "ix_claim_claimant_created", "claims", ["claimant_id", "created_at", "id"], schema=schema
    )
    op.create_index(
        "uq_claim_active_pair",
        "claims",
        ["found_post_id", "claimant_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('PENDING','APPROVED')"),
        sqlite_where=sa.text("status IN ('PENDING','APPROVED')"),
        schema=schema,
    )
    op.create_index(
        "uq_claim_post_winner",
        "claims",
        ["found_post_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('APPROVED','RETURNED')"),
        sqlite_where=sa.text("status IN ('APPROVED','RETURNED')"),
        schema=schema,
    )
    op.create_table(
        "claim_evidence",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("claim_id", sa.Uuid(), sa.ForeignKey(fk("claims")), nullable=False),
        sa.Column("private_content", sa.Text(), nullable=False),
        sa.Column("file_path", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(trim(private_content)) > 0", name="ck_evidence_content"),
        schema=schema,
    )
    op.create_index("ix_claim_evidence_claim_id", "claim_evidence", ["claim_id"], schema=schema)
    op.create_table(
        "returns",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("claim_id", sa.Uuid(), sa.ForeignKey(fk("claims")), nullable=False, unique=True),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("handed_over_at", sa.DateTime(timezone=True)),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('ARRANGED','HANDED_OVER','CONFIRMED')", name="ck_return_status"
        ),
        schema=schema,
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey(fk("users")), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("claim_id", sa.Uuid(), sa.ForeignKey(fk("claims")), nullable=False),
        sa.Column("found_post_id", sa.Uuid(), sa.ForeignKey(fk("posts")), nullable=False),
        sa.Column("previous_version", sa.Integer()),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        schema=schema,
    )
    op.create_table(
        "outbox_events",
        sa.Column("event_id", sa.Uuid(), primary_key=True),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        schema=schema,
    )


def downgrade(schema=None):
    for table in (
        "outbox_events",
        "audit_logs",
        "returns",
        "claim_evidence",
        "claims",
        "posts",
        "revoked_tokens",
        "users",
    ):
        op.drop_table(table, schema=schema)
