"""Add tag field to Transaction model

Revision ID: ec1bfb3bb2a8
Revises: 
Create Date: 2024-07-10 20:52:18.543410

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ec1bfb3bb2a8'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('transaction', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tag', sa.String(length=100), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('transaction', schema=None) as batch_op:
        batch_op.drop_column('tag')

    # ### end Alembic commands ###
