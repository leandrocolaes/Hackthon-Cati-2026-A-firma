"""Referencia publica do usuario (RF22: perfil publico sem expor o id interno).

Revision ID: 0004_ref_publica_usuarios
Revises: 0003_arquivos_fotos
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_ref_publica_usuarios"
down_revision = "0003_arquivos_fotos"
branch_labels = None
depends_on = None

# 16 caracteres hexadecimais aleatorios. Volatil: o PostgreSQL calcula um valor por
# linha, inclusive para as contas que ja existem (ADD COLUMN reescreve a tabela).
REF_ALEATORIA = "substr(md5(random()::text || clock_timestamp()::text), 1, 16)"


def upgrade() -> None:
    op.add_column("usuarios", sa.Column(
        "ref_publica", sa.String(length=32), server_default=sa.text(REF_ALEATORIA), nullable=False))
    op.create_unique_constraint("uq_usuarios_ref_publica", "usuarios", ["ref_publica"])


def downgrade() -> None:
    op.drop_constraint("uq_usuarios_ref_publica", "usuarios", type_="unique")
    op.drop_column("usuarios", "ref_publica")
