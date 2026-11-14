"""Marca do aviso de lance superado (RF26: no maximo um aviso por usuario e leilao).

Revision ID: 0005_aviso_lance_superado
Revises: 0004_ref_publica_usuarios
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_aviso_lance_superado"
down_revision = "0004_ref_publica_usuarios"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("participantes", sa.Column("avisado_superado_em", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("participantes", "avisado_superado_em")
