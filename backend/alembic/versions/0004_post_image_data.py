"""Store post image bytes in the database.

Revision ID: 0004_post_image_data
Revises: 0003_integrated_system
"""

import sqlalchemy as sa

from alembic import op

revision = "0004_post_image_data"
down_revision = "0003_integrated_system"
branch_labels = None
depends_on = None


def upgrade(schema=None):
    op.add_column("post_images", sa.Column("image_data", sa.LargeBinary()), schema=schema)


def downgrade(schema=None):
    with op.batch_alter_table("post_images", schema=schema) as batch:
        batch.drop_column("image_data")
