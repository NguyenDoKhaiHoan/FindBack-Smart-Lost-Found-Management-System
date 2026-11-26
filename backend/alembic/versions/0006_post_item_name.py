"""Store a custom item name on a post.

Revision ID: 0006_post_item_name
Revises: 0005_ai_embeddings
"""

import sqlalchemy as sa

from alembic import op

revision = "0006_post_item_name"
down_revision = "0005_ai_embeddings"
branch_labels = None
depends_on = None


def upgrade(schema=None):
    op.add_column("posts", sa.Column("item_name", sa.String(100)), schema=schema)


def downgrade(schema=None):
    with op.batch_alter_table("posts", schema=schema) as batch:
        batch.drop_column("item_name")
