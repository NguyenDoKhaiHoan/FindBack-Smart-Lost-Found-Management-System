"""Store AI embeddings for public post text and images.

Revision ID: 0005_ai_embeddings
Revises: 0004_post_image_data
"""

import sqlalchemy as sa

from alembic import op

revision = "0005_ai_embeddings"
down_revision = "0004_post_image_data"
branch_labels = None
depends_on = None


def upgrade(schema=None):
    for table in ("posts", "post_images"):
        op.add_column(table, sa.Column("ai_embedding_key", sa.String(64)), schema=schema)
        op.add_column(table, sa.Column("ai_embedding", sa.JSON()), schema=schema)


def downgrade(schema=None):
    for table in ("post_images", "posts"):
        with op.batch_alter_table(table, schema=schema) as batch:
            batch.drop_column("ai_embedding")
            batch.drop_column("ai_embedding_key")
