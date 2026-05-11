"""add sla tier timing columns to client

Revision ID: a1c2e3f4b5d6
Revises: b835da9262b1
Create Date: 2026-05-11 13:57:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1c2e3f4b5d6'
down_revision = 'b835da9262b1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('clients', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sla1_time_hours', sa.Numeric(precision=6, scale=2), nullable=True))
        batch_op.add_column(sa.Column('sla2_time_hours', sa.Numeric(precision=6, scale=2), nullable=True))
        batch_op.add_column(sa.Column('sla3_time_hours', sa.Numeric(precision=6, scale=2), nullable=True))


def downgrade():
    with op.batch_alter_table('clients', schema=None) as batch_op:
        batch_op.drop_column('sla3_time_hours')
        batch_op.drop_column('sla2_time_hours')
        batch_op.drop_column('sla1_time_hours')
