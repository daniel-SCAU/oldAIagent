"""add intent and sentiment columns

Revision ID: 0002
Revises: 0001
Create Date: 2024-06-01

"""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('Chat') as batch_op:
        batch_op.add_column(sa.Column('intent', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('sentiment', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('Chat') as batch_op:
        batch_op.drop_column('intent')
        batch_op.drop_column('sentiment')
