"""Initial users and notifications tables

Revision ID: 20261117_01
Revises:
Create Date: 2026-11-17 01:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20261117_01'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), server_default=sa.text("'USER'"), nullable=False),
        sa.Column('status', sa.String(length=20), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.CheckConstraint("role IN ('USER', 'ADMIN', 'user', 'admin')", name='ck_users_role'),
        sa.CheckConstraint("status IN ('ACTIVE', 'SUSPENDED', 'DISABLED')", name='ck_users_status'),
        sa.CheckConstraint("length(trim(email)) > 0 AND email = lower(trim(email))", name='ck_users_email_normalized'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 2. Create notifications table
    op.create_table(
        'notifications',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('recipient_id', sa.Uuid(), nullable=False),
        sa.Column('event_id', sa.Uuid(), nullable=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('resource_type', sa.String(length=30), nullable=True),
        sa.Column('resource_id', sa.Uuid(), nullable=True),
        sa.Column('metadata', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('is_read', sa.Boolean(), server_default=sa.text('FALSE'), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['recipient_id'], ['users.id'], name='fk_notifications_recipient', ondelete='CASCADE'),
        sa.CheckConstraint("resource_type IS NULL OR resource_type IN ('CLAIM', 'POST', 'RETURN', 'REPORT', 'MATCH')", name='ck_notifications_resource_type'),
        sa.CheckConstraint('(resource_type IS NULL AND resource_id IS NULL) OR (resource_type IS NOT NULL AND resource_id IS NOT NULL)', name='ck_notifications_resource_pair'),
        sa.CheckConstraint('(is_read = FALSE AND read_at IS NULL) OR (is_read = TRUE AND read_at IS NOT NULL)', name='ck_notifications_read_state'),
        sa.CheckConstraint('length(trim(event_type)) > 0', name='ck_notifications_event_type_not_empty'),
        sa.CheckConstraint('length(trim(title)) > 0', name='ck_notifications_title_not_empty'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notifications_recipient_id'), 'notifications', ['recipient_id'], unique=False)
    op.create_index('ix_notifications_recipient_created', 'notifications', ['recipient_id', sa.text('created_at DESC')], unique=False)
    op.create_index(
        'ix_notifications_unread',
        'notifications',
        ['recipient_id', sa.text('created_at DESC')],
        unique=False,
        postgresql_where=sa.text('is_read = FALSE')
    )
    op.create_index(
        'ix_notifications_event_id_unique',
        'notifications',
        ['event_id'],
        unique=True,
        postgresql_where=sa.text('event_id IS NOT NULL')
    )


def downgrade() -> None:
    op.drop_index('ix_notifications_event_id_unique', table_name='notifications')
    op.drop_index('ix_notifications_unread', table_name='notifications')
    op.drop_index('ix_notifications_recipient_created', table_name='notifications')
    op.drop_index(op.f('ix_notifications_recipient_id'), table_name='notifications')
    op.drop_table('notifications')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
