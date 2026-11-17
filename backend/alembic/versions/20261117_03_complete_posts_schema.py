"""Complete posts schema with categories, post_images, coordinates, and item details

Revision ID: 20261117_03
Revises: 20261117_02
Create Date: 2026-11-17 18:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20261117_03'
down_revision: Union[str, None] = '20261117_02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create categories table
    op.create_table(
        'categories',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug', name='uq_categories_slug')
    )
    op.create_index('ix_categories_slug', 'categories', ['slug'], unique=True)

    # 2. Add foreign key constraint and index for posts.category_id -> categories.id
    op.create_foreign_key(
        'fk_posts_category',
        'posts',
        'categories',
        ['category_id'],
        ['id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_posts_category_id', 'posts', ['category_id'], unique=False)

    # 3. Add location GPS coordinates and item details to posts
    op.add_column('posts', sa.Column('latitude', sa.Numeric(precision=9, scale=6), nullable=True))
    op.add_column('posts', sa.Column('longitude', sa.Numeric(precision=9, scale=6), nullable=True))
    op.add_column('posts', sa.Column('brand', sa.String(length=100), nullable=True))
    op.add_column('posts', sa.Column('color', sa.String(length=100), nullable=True))
    op.add_column('posts', sa.Column('event_time', sa.DateTime(timezone=True), nullable=True))

    # 4. Add check constraints for GPS coordinates on posts
    op.create_check_constraint(
        'ck_posts_latitude',
        'posts',
        'latitude IS NULL OR (latitude BETWEEN -90.0 AND 90.0)'
    )
    op.create_check_constraint(
        'ck_posts_longitude',
        'posts',
        'longitude IS NULL OR (longitude BETWEEN -180.0 AND 180.0)'
    )
    op.create_check_constraint(
        'ck_posts_coordinates',
        'posts',
        '(latitude IS NULL) = (longitude IS NULL)'
    )

    # 5. Create post_images table
    op.create_table(
        'post_images',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('post_id', sa.Uuid(), nullable=False),
        sa.Column('image_url', sa.String(length=500), nullable=False),
        sa.Column('display_order', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['post_id'], ['posts.id'], name='fk_post_images_post', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_post_images_post_id', 'post_images', ['post_id'], unique=False)
    op.create_index('ix_post_images_post_order', 'post_images', ['post_id', 'display_order'], unique=False)


def downgrade() -> None:
    # 1. Drop post_images table
    op.drop_index('ix_post_images_post_order', table_name='post_images')
    op.drop_index('ix_post_images_post_id', table_name='post_images')
    op.drop_table('post_images')

    # 2. Drop GPS check constraints from posts
    op.drop_constraint('ck_posts_coordinates', 'posts', type_='check')
    op.drop_constraint('ck_posts_longitude', 'posts', type_='check')
    op.drop_constraint('ck_posts_latitude', 'posts', type_='check')

    # 3. Drop item details and GPS columns from posts
    op.drop_column('posts', 'event_time')
    op.drop_column('posts', 'color')
    op.drop_column('posts', 'brand')
    op.drop_column('posts', 'longitude')
    op.drop_column('posts', 'latitude')

    # 4. Drop category FK and index from posts
    op.drop_index('ix_posts_category_id', table_name='posts')
    op.drop_constraint('fk_posts_category', 'posts', type_='foreignkey')

    # 5. Drop categories table
    op.drop_index('ix_categories_slug', table_name='categories')
    op.drop_table('categories')
