"""Estado persistido de uma venda; transicoes pertencem aos servicos futuros."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, Index, Integer, Numeric, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.item import Item
    from app.models.lance import Lance
    from app.models.participante import Participante
    from app.models.tentativa_lance import TentativaLance
    from app.models.usuario import Usuario


class Leilao(Base):
    __tablename__ = "leiloes"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('agendado','em_andamento','vendido','encerrado_sem_lances','cancelado')",
            name="ck_leiloes_estado",
        ),
        CheckConstraint("preco_atual >= preco_inicial", name="ck_leiloes_preco_atual"),
        CheckConstraint("termino_original > inicio", name="ck_leiloes_termino_original"),
        CheckConstraint("termino_vigente >= termino_original", name="ck_leiloes_termino_vigente"),
        CheckConstraint(
            "(estado = 'vendido') = (lance_vencedor_id IS NOT NULL)",
            name="ck_leiloes_vencedor",
        ),
        CheckConstraint(
            "(estado IN ('vendido','encerrado_sem_lances','cancelado')) = (encerrado_em IS NOT NULL)",
            name="ck_leiloes_encerramento",
        ),
        Index(
            "uq_leiloes_item_ativo", "item_id", unique=True,
            postgresql_where=text("estado IN ('agendado','em_andamento')"),
        ),
        Index("ix_leiloes_estado_inicio", "estado", "inicio"),
        Index("ix_leiloes_estado_termino_vigente", "estado", "termino_vigente"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("itens.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    comitente_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    preco_inicial: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    preco_atual: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    termino_original: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    termino_vigente: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    estado: Mapped[str] = mapped_column(String, nullable=False, server_default=text("'agendado'"))
    lider_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=True
    )
    lance_vencedor_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("lances.id", name="fk_leiloes_lance_vencedor", ondelete="RESTRICT", use_alter=True),
        nullable=True,
    )
    encerrado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    versao: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    prorrogacoes: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    item: Mapped["Item"] = relationship(back_populates="leiloes")
    comitente: Mapped["Usuario"] = relationship(foreign_keys=[comitente_id])
    lider: Mapped["Usuario | None"] = relationship(foreign_keys=[lider_id])
    # Leitura apenas: o fechamento atribui lance_vencedor_id e estado atomicamente.
    # Evita ciclo de flush entre Leilao e Lance e UPDATE intermediario incoerente.
    lance_vencedor: Mapped["Lance | None"] = relationship(
        foreign_keys=[lance_vencedor_id], viewonly=True
    )
    lances: Mapped[list["Lance"]] = relationship(
        back_populates="leilao", foreign_keys="Lance.leilao_id", passive_deletes="all"
    )
    tentativas: Mapped[list["TentativaLance"]] = relationship(
        back_populates="leilao", passive_deletes="all"
    )
    participantes: Mapped[list["Participante"]] = relationship(
        back_populates="leilao", passive_deletes="all"
    )
