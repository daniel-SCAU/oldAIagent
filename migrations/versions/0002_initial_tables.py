"""create chat and task tables

Revision ID: 0002
Revises: 0001
Create Date: 2024-05-26

"""
from alembic import op
import sqlalchemy as sa


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'Chat',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('sender', sa.Text, nullable=False),
        sa.Column('app', sa.Text, nullable=False),
        sa.Column('message', sa.Text, nullable=False),
        sa.Column('conversation_id', sa.Text, nullable=True),
        sa.Column('contact_id', sa.Integer, sa.ForeignKey('contacts.id'), nullable=True),
        sa.Column('category', sa.Text, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()')),
    )
    op.create_table(
        'summary_tasks',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('conversation_id', sa.Text, nullable=False),
        sa.Column('status', sa.Text, nullable=False, server_default='pending'),
        sa.Column('summary', sa.Text, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()')),
    )
    op.create_table(
        'followup_tasks',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('conversation_id', sa.Text, nullable=False),
        sa.Column('task', sa.Text, nullable=False),
        sa.Column('status', sa.Text, nullable=False, server_default='pending'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()')),
    )


def downgrade():
    op.drop_table('followup_tasks')
    op.drop_table('summary_tasks')
    op.drop_table('Chat')
