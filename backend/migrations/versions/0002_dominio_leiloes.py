"""Cria itens, fotos, leiloes, lances, tentativas e participantes.

Revision ID: 0002_dominio_leiloes
Revises: 0001_usuarios_sessoes
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_dominio_leiloes"
down_revision = "0001_usuarios_sessoes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('itens',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('usuario_id', sa.BigInteger(), nullable=False),
    sa.Column('nome', sa.String(length=100), nullable=False),
    sa.Column('descricao', sa.String(length=2000), nullable=False),
    sa.Column('categoria', sa.String(), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_itens_usuario_id'), 'itens', ['usuario_id'], unique=False)
    op.create_table('fotos_itens',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('item_id', sa.BigInteger(), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('chave_armazenamento', sa.Text(), nullable=True),
    sa.Column('ordem', sa.Integer(), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('ordem >= 0', name='ck_fotos_itens_ordem'),
    sa.ForeignKeyConstraint(['item_id'], ['itens.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('item_id', 'ordem', name='uq_fotos_itens_item_ordem')
    )
    op.create_table('leiloes',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('item_id', sa.BigInteger(), nullable=False),
    sa.Column('comitente_id', sa.BigInteger(), nullable=False),
    sa.Column('preco_inicial', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('preco_atual', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('inicio', sa.DateTime(timezone=True), nullable=False),
    sa.Column('termino_original', sa.DateTime(timezone=True), nullable=False),
    sa.Column('termino_vigente', sa.DateTime(timezone=True), nullable=False),
    sa.Column('estado', sa.String(), server_default=sa.text("'agendado'"), nullable=False),
    sa.Column('lider_id', sa.BigInteger(), nullable=True),
    sa.Column('lance_vencedor_id', sa.BigInteger(), nullable=True),
    sa.Column('encerrado_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('versao', sa.BigInteger(), server_default=sa.text('0'), nullable=False),
    sa.Column('prorrogacoes', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.CheckConstraint("(estado = 'vendido') = (lance_vencedor_id IS NOT NULL)", name='ck_leiloes_vencedor'),
    sa.CheckConstraint("(estado IN ('vendido','encerrado_sem_lances','cancelado')) = (encerrado_em IS NOT NULL)", name='ck_leiloes_encerramento'),
    sa.CheckConstraint("estado IN ('agendado','em_andamento','vendido','encerrado_sem_lances','cancelado')", name='ck_leiloes_estado'),
    sa.CheckConstraint('preco_atual >= preco_inicial', name='ck_leiloes_preco_atual'),
    sa.CheckConstraint('termino_original > inicio', name='ck_leiloes_termino_original'),
    sa.CheckConstraint('termino_vigente >= termino_original', name='ck_leiloes_termino_vigente'),
    sa.ForeignKeyConstraint(['comitente_id'], ['usuarios.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['item_id'], ['itens.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['lider_id'], ['usuarios.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_leiloes_comitente_id'), 'leiloes', ['comitente_id'], unique=False)
    op.create_index('ix_leiloes_estado_inicio', 'leiloes', ['estado', 'inicio'], unique=False)
    op.create_index('ix_leiloes_estado_termino_vigente', 'leiloes', ['estado', 'termino_vigente'], unique=False)
    op.create_index(op.f('ix_leiloes_item_id'), 'leiloes', ['item_id'], unique=False)
    op.create_index('uq_leiloes_item_ativo', 'leiloes', ['item_id'], unique=True, postgresql_where=sa.text("estado IN ('agendado','em_andamento')"))
    op.create_table('lances',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('leilao_id', sa.BigInteger(), nullable=False),
    sa.Column('usuario_id', sa.BigInteger(), nullable=False),
    sa.Column('valor', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('valor > 0', name='ck_lances_valor'),
    sa.ForeignKeyConstraint(['leilao_id'], ['leiloes.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_lances_leilao_criado_em_id', 'lances', ['leilao_id', 'criado_em', 'id'], unique=False)
    op.create_index(op.f('ix_lances_usuario_id'), 'lances', ['usuario_id'], unique=False)
    op.create_table('tentativas_lance',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('usuario_id', sa.BigInteger(), nullable=False),
    sa.Column('leilao_id', sa.BigInteger(), nullable=False),
    sa.Column('chave', sa.UUID(), nullable=False),
    sa.Column('valor_solicitado', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('lance_id', sa.BigInteger(), nullable=True),
    sa.Column('situacao', sa.String(), nullable=False),
    sa.Column('status_http', sa.Integer(), nullable=False),
    sa.Column('resposta_original', postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=False),
    sa.CheckConstraint("situacao IN ('aceita','recusada')", name='ck_tentativas_lance_situacao'),
    sa.ForeignKeyConstraint(['lance_id'], ['lances.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['leilao_id'], ['leiloes.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('lance_id', name='uq_tentativas_lance_lance'),
    sa.UniqueConstraint('usuario_id', 'chave', name='uq_tentativas_lance_usuario_chave')
    )
    op.create_index(op.f('ix_tentativas_lance_leilao_id'), 'tentativas_lance', ['leilao_id'], unique=False)
    op.create_table('participantes',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('leilao_id', sa.BigInteger(), nullable=False),
    sa.Column('usuario_id', sa.BigInteger(), nullable=False),
    sa.Column('numero', sa.Integer(), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['leilao_id'], ['leiloes.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('leilao_id', 'numero', name='uq_participantes_leilao_numero'),
    sa.UniqueConstraint('leilao_id', 'usuario_id', name='uq_participantes_leilao_usuario')
    )
    op.create_index(op.f('ix_participantes_usuario_id'), 'participantes', ['usuario_id'], unique=False)
    op.create_foreign_key('fk_leiloes_lance_vencedor', 'leiloes', 'lances', ['lance_vencedor_id'], ['id'], ondelete='RESTRICT')


def downgrade() -> None:
    # Rompe o ciclo antes de remover lances e leiloes.
    op.drop_constraint("fk_leiloes_lance_vencedor", "leiloes", type_="foreignkey")
    op.drop_table("participantes")
    op.drop_table("tentativas_lance")
    op.drop_table("lances")
    op.drop_table("leiloes")
    op.drop_table("fotos_itens")
    op.drop_table("itens")
