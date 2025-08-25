"""add search vector to chat

Revision ID: 0003
Revises: 0002
Create Date: 2024-06-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('Chat', sa.Column('search_vector', postgresql.TSVECTOR(), nullable=True))
    op.execute("UPDATE \"Chat\" SET search_vector = to_tsvector('english', message)")
    op.create_index('chat_search_vector_idx', 'Chat', ['search_vector'], unique=False, postgresql_using='gin')


def downgrade():
    op.drop_index('chat_search_vector_idx', table_name='Chat')
    op.drop_column('Chat', 'search_vector')
