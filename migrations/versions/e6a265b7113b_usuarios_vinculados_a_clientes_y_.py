"""usuarios vinculados a clientes y productores

Revision ID: e6a265b7113b
Revises: 
Create Date: 2026-03-28 00:46:24.631762
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e6a265b7113b'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cliente_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('proveedor_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_users_cliente_id',
            'clientes',
            ['cliente_id'],
            ['id']
        )
        batch_op.create_foreign_key(
            'fk_users_proveedor_id',
            'proveedores',
            ['proveedor_id'],
            ['id']
        )


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint('fk_users_proveedor_id', type_='foreignkey')
        batch_op.drop_constraint('fk_users_cliente_id', type_='foreignkey')
        batch_op.drop_column('proveedor_id')
        batch_op.drop_column('cliente_id')