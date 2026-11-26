"""Add opt-in hotspot areas and persistent DBSCAN configuration."""

import sqlalchemy as sa

from alembic import op

revision = "0007_hotspot_analysis"
down_revision = "0006_post_item_name"
branch_labels = None
depends_on = None

FILTER = "type = 'LOST' AND hotspot_zone IS NOT NULL AND deleted_at IS NULL AND is_hidden IS FALSE"


def upgrade(schema=None):
    op.add_column("posts", sa.Column("hotspot_zone", sa.String(16)), schema=schema)
    op.create_index(
        "ix_posts_hotspot_period",
        "posts",
        ["event_time", "location_code", "category_id"],
        schema=schema,
        sqlite_where=sa.text(FILTER),
        postgresql_where=sa.text(FILTER),
    )
    table = op.create_table(
        "hotspot_settings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("eps_meters", sa.Integer, nullable=False),
        sa.Column("min_samples", sa.Integer, nullable=False),
        sa.Column("period_days", sa.Integer, nullable=False),
        sa.Column("medium_count", sa.Integer, nullable=False),
        sa.Column("high_count", sa.Integer, nullable=False),
        sa.Column("very_high_count", sa.Integer, nullable=False),
        sa.CheckConstraint("id = 1", name="ck_hotspot_settings_singleton"),
        schema=schema,
    )
    op.bulk_insert(
        table,
        [
            dict(
                id=1,
                eps_meters=200,
                min_samples=5,
                period_days=30,
                medium_count=10,
                high_count=20,
                very_high_count=35,
            )
        ],
    )


def downgrade(schema=None):
    op.drop_table("hotspot_settings", schema=schema)
    op.drop_index("ix_posts_hotspot_period", table_name="posts", schema=schema)
    with op.batch_alter_table("posts", schema=schema) as batch:
        batch.drop_column("hotspot_zone")
