"""Add shared Identity, Posts, Matching, Returns and Admin storage.

Revision ID: 0003_integrated_system
Revises: 0002_claim_decisions
"""

from uuid import UUID

import sqlalchemy as sa

from alembic import op

revision = "0003_integrated_system"
down_revision = "0002_claim_decisions"
branch_labels = None
depends_on = None

POST_COLUMNS = (
    "category_id",
    "title",
    "description",
    "location",
    "area",
    "location_code",
    "event_time",
    "brand",
    "material",
    "color",
    "color_code",
    "latitude",
    "longitude",
    "search_text",
    "created_at",
    "updated_at",
    "moderated_by",
    "moderated_at",
    "moderation_reason",
)
USER_COLUMNS = ("email", "password_hash", "full_name", "phone", "avatar_url", "created_at")
RETURN_COLUMNS = ("arranged_at", "scheduled_at", "meeting_note")


def timestamp(name, *, nullable=True, default=None):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable, server_default=default)


def foreign_key(name, table, schema, *, nullable=False, primary_key=False, ondelete=None):
    target = f"{schema}.{table}.id" if schema else f"{table}.id"
    return sa.Column(
        name,
        sa.Uuid(),
        sa.ForeignKey(target, ondelete=ondelete),
        nullable=nullable,
        primary_key=primary_key,
    )


def upgrade(schema=None):
    with op.batch_alter_table("users", schema=schema) as batch:
        batch.add_column(sa.Column("email", sa.String(320)))
        batch.add_column(sa.Column("password_hash", sa.String(255)))
        batch.add_column(sa.Column("full_name", sa.String(100)))
        batch.add_column(sa.Column("phone", sa.String(32)))
        batch.add_column(sa.Column("avatar_url", sa.String(2048)))
        batch.add_column(timestamp("created_at", nullable=False, default=sa.func.now()))
        batch.create_unique_constraint("uq_users_email", ["email"])

    category = op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        schema=schema,
    )
    op.bulk_insert(
        category,
        [
            {"id": UUID(int=index), "name": name, "is_active": True}
            for index, name in enumerate(
                ("Giấy tờ", "Ví và túi xách", "Thiết bị điện tử", "Chìa khóa", "Khác"),
                start=1,
            )
        ],
    )

    with op.batch_alter_table("posts", schema=schema) as batch:
        batch.add_column(sa.Column("category_id", sa.Uuid()))
        batch.add_column(sa.Column("title", sa.String(255)))
        batch.add_column(sa.Column("description", sa.Text()))
        batch.add_column(sa.Column("location", sa.String(255)))
        batch.add_column(sa.Column("area", sa.String(100)))
        batch.add_column(sa.Column("location_code", sa.String(50)))
        batch.add_column(timestamp("event_time"))
        for field, size in (("brand", 100), ("material", 100), ("color", 50), ("color_code", 20)):
            batch.add_column(sa.Column(field, sa.String(size)))
        batch.add_column(sa.Column("latitude", sa.Numeric(9, 6)))
        batch.add_column(sa.Column("longitude", sa.Numeric(9, 6)))
        batch.add_column(sa.Column("search_text", sa.Text()))
        batch.add_column(timestamp("created_at", nullable=False, default=sa.func.now()))
        batch.add_column(timestamp("updated_at", nullable=False, default=sa.func.now()))
        batch.add_column(sa.Column("moderated_by", sa.Uuid()))
        batch.add_column(timestamp("moderated_at"))
        batch.add_column(sa.Column("moderation_reason", sa.Text()))
        batch.create_foreign_key(
            "fk_posts_category", "categories", ["category_id"], ["id"], referent_schema=schema
        )
        batch.create_foreign_key(
            "fk_posts_moderator", "users", ["moderated_by"], ["id"], referent_schema=schema
        )
        batch.create_index("ix_posts_category_id", ["category_id"])
        batch.create_index(
            "ix_posts_public_created", ["is_hidden", "deleted_at", "created_at", "id"]
        )

    with op.batch_alter_table("returns", schema=schema) as batch:
        batch.add_column(timestamp("arranged_at"))
        batch.add_column(timestamp("scheduled_at"))
        batch.add_column(sa.Column("meeting_note", sa.Text()))

    op.create_table(
        "refresh_tokens",
        sa.Column("digest", sa.String(64), primary_key=True),
        foreign_key("user_id", "users", schema),
        sa.Column("token_version", sa.Integer(), nullable=False),
        timestamp("expires_at", nullable=False),
        timestamp("used_at"),
        schema=schema,
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"], schema=schema)
    op.create_table(
        "post_images",
        sa.Column("id", sa.Uuid(), primary_key=True),
        foreign_key("post_id", "posts", schema),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        timestamp("created_at", nullable=False),
        schema=schema,
    )
    op.create_index("ix_post_images_post_id", "post_images", ["post_id"], schema=schema)
    op.create_table(
        "match_generations",
        foreign_key("source_id", "posts", schema, primary_key=True),
        sa.Column("rule_version", sa.String(50), nullable=False),
        timestamp("calculated_at", nullable=False),
        sa.Column("fingerprints", sa.JSON(), nullable=False),
        schema=schema,
    )
    gen = f"{schema}.match_generations.source_id" if schema else "match_generations.source_id"
    op.create_table(
        "match_results",
        sa.Column("source_id", sa.Uuid(), sa.ForeignKey(gen, ondelete="CASCADE"), primary_key=True),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("score_data", sa.JSON(), nullable=False),
        schema=schema,
    )
    op.create_index("ix_match_results_id", "match_results", ["id"], schema=schema)

    notification = op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        foreign_key("recipient_id", "users", schema),
        sa.Column("event_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.String(30), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        timestamp("read_at"),
        timestamp("created_at", nullable=False),
        schema=schema,
    )
    op.create_index(
        "ix_notifications_recipient_created",
        "notifications",
        ["recipient_id", "created_at", "id"],
        schema=schema,
    )
    backfill_notifications(notification, schema)

    op.create_table(
        "reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        foreign_key("reporter_id", "users", schema),
        foreign_key("post_id", "posts", schema),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("resolution_note", sa.Text()),
        foreign_key("reviewed_by", "users", schema, nullable=True),
        timestamp("reviewed_at"),
        timestamp("created_at", nullable=False),
        sa.CheckConstraint(
            "status IN ('PENDING','REVIEWING','RESOLVED','DISMISSED')", name="ck_report_status"
        ),
        schema=schema,
    )
    open_report = sa.text("status IN ('PENDING','REVIEWING')")
    op.create_index(
        "uq_open_report_per_user_post",
        "reports",
        ["reporter_id", "post_id"],
        unique=True,
        postgresql_where=open_report,
        sqlite_where=open_report,
        schema=schema,
    )
    op.create_index("ix_reports_status", "reports", ["status"], schema=schema)
    op.create_index("ix_reports_post_id", "reports", ["post_id"], schema=schema)
    op.create_table(
        "moderation_audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        foreign_key("actor_id", "users", schema),
        foreign_key("post_id", "posts", schema),
        foreign_key("report_id", "reports", schema, nullable=True),
        sa.Column("action", sa.String(30), nullable=False),
        timestamp("occurred_at", nullable=False),
        schema=schema,
    )


def backfill_notifications(notification, schema):
    labels = {
        "claim.created": ("CLAIM_CREATED", "Yêu cầu nhận đồ mới"),
        "claim.approved": ("CLAIM_APPROVED", "Yêu cầu nhận đồ được duyệt"),
        "claim.rejected": ("CLAIM_REJECTED", "Yêu cầu nhận đồ bị từ chối"),
        "claim.completed": ("CLAIM_COMPLETED", "Trao trả đã được xác nhận"),
        "claim.evidence_added": ("CLAIM_EVIDENCE_ADDED", "Bằng chứng nhận đồ được bổ sung"),
        "return.arranged": ("RETURN_ARRANGED", "Phiên trao trả đã được lập"),
        "return.handed_over": ("RETURN_HANDED_OVER", "Chủ tin đã ghi nhận giao đồ"),
    }
    connection = op.get_bind()
    outbox = sa.table(
        "outbox_events",
        sa.column("event_id", sa.Uuid()),
        sa.column("type", sa.String()),
        sa.column("payload", sa.JSON()),
        sa.column("occurred_at", sa.DateTime(timezone=True)),
        schema=schema,
    )
    users = sa.table("users", sa.column("id", sa.Uuid()), schema=schema)
    for event in connection.execute(sa.select(outbox).where(outbox.c.type.in_(labels))):
        recipient = UUID(event.payload["recipient_id"])
        if connection.scalar(sa.select(users.c.id).where(users.c.id == recipient)) is None:
            continue
        kind, title = labels[event.type]
        connection.execute(
            notification.insert().values(
                id=event.event_id,
                event_id=event.event_id,
                recipient_id=recipient,
                type=kind,
                title=title,
                message=title,
                resource_type="CLAIM",
                resource_id=UUID(event.payload["claim_id"]),
                created_at=event.occurred_at,
            )
        )


def downgrade(schema=None):
    for table in (
        "moderation_audit_logs",
        "reports",
        "notifications",
        "match_results",
        "match_generations",
        "post_images",
        "refresh_tokens",
    ):
        op.drop_table(table, schema=schema)
    with op.batch_alter_table("returns", schema=schema) as batch:
        for field in RETURN_COLUMNS:
            batch.drop_column(field)
    with op.batch_alter_table("posts", schema=schema) as batch:
        batch.drop_index("ix_posts_public_created")
        batch.drop_index("ix_posts_category_id")
        batch.drop_constraint("fk_posts_moderator", type_="foreignkey")
        batch.drop_constraint("fk_posts_category", type_="foreignkey")
        for field in POST_COLUMNS:
            batch.drop_column(field)
    op.drop_table("categories", schema=schema)
    with op.batch_alter_table("users", schema=schema) as batch:
        batch.drop_constraint("uq_users_email", type_="unique")
        for field in USER_COLUMNS:
            batch.drop_column(field)
