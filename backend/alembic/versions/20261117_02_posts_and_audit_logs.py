"""Add posts and audit_logs tables

Revision ID: 20261117_02
Revises: 20261117_01
Create Date: 2026-11-17 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20261117_02'
down_revision: Union[str, None] = '20261117_01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create posts table
    op.create_table(
        'posts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('type', sa.String(length=10), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('category_id', sa.Uuid(), nullable=True),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('area', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=20), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column('moderated_by', sa.Uuid(), nullable=True),
        sa.Column('moderated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('moderation_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_posts_user', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['moderated_by'], ['users.id'], name='fk_posts_moderated_by', ondelete='SET NULL'),
        sa.CheckConstraint("type IN ('LOST', 'FOUND')", name='ck_posts_type'),
        sa.CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'HIDDEN', 'CLOSED')", name='ck_posts_status'),
        sa.CheckConstraint('length(trim(title)) > 0', name='ck_posts_title_not_empty'),
        sa.CheckConstraint('length(trim(description)) > 0', name='ck_posts_description_not_empty'),
        sa.CheckConstraint(
            '(moderated_by IS NULL AND moderated_at IS NULL AND moderation_reason IS NULL) OR '
            '(moderated_by IS NOT NULL AND moderated_at IS NOT NULL AND length(trim(moderation_reason)) > 0)',
            name='ck_posts_moderation'
        ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_posts_user_id'), 'posts', ['user_id'], unique=False)
    op.create_index('ix_posts_status', 'posts', ['status'], unique=False)
    op.create_index('ix_posts_type', 'posts', ['type'], unique=False)
    op.create_index('ix_posts_created_at', 'posts', [sa.text('created_at DESC')], unique=False)
    op.create_index('ix_posts_admin_list', 'posts', ['status', 'type', sa.text('created_at DESC')], unique=False)

    # 2. Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('actor_id', sa.Uuid(), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('target_type', sa.String(length=50), nullable=False),
        sa.Column('target_id', sa.Uuid(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('old_status', sa.String(length=20), nullable=True),
        sa.Column('new_status', sa.String(length=20), nullable=True),
        sa.Column('metadata', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name='fk_audit_logs_actor', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_audit_logs_actor', 'audit_logs', ['actor_id', sa.text('created_at DESC')], unique=False)
    op.create_index('ix_audit_logs_target', 'audit_logs', ['target_type', 'target_id', sa.text('created_at DESC')], unique=False)
    op.create_index('ix_audit_logs_created', 'audit_logs', [sa.text('created_at DESC')], unique=False)


def downgrade() -> None:
    op.drop_index('ix_audit_logs_created', table_name='audit_logs')
    op.drop_index('ix_audit_logs_target', table_name='audit_logs')
    op.drop_index('ix_audit_logs_actor', table_name='audit_logs')
    op.drop_table('audit_logs')

    op.drop_index('ix_posts_admin_list', table_name='posts')
    op.drop_index('ix_posts_created_at', table_name='posts')
    op.drop_index('ix_posts_type', table_name='posts')
    op.drop_index('ix_posts_status', table_name='posts')
    op.drop_index(op.f('ix_posts_user_id'), table_name='posts')
    op.drop_table('posts')
