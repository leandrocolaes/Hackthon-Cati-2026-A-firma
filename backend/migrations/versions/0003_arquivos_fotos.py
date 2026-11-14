"""Cria arquivos_fotos (bytes das fotos enviadas, RF07).

Revision ID: 0003_arquivos_fotos
Revises: 0002_dominio_leiloes
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_arquivos_fotos"
down_revision = "0002_dominio_leiloes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('arquivos_fotos',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('referencia', sa.String(length=64), nullable=False),
    sa.Column('usuario_id', sa.BigInteger(), nullable=False),
    sa.Column('tipo', sa.String(), nullable=False),
    sa.Column('tamanho', sa.Integer(), nullable=False),
    sa.Column('dados', sa.LargeBinary(), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('tamanho > 0', name='ck_arquivos_fotos_tamanho'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('referencia')
    )
    op.create_index(op.f('ix_arquivos_fotos_usuario_id'), 'arquivos_fotos', ['usuario_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_arquivos_fotos_usuario_id'), table_name='arquivos_fotos')
    op.drop_table('arquivos_fotos')
