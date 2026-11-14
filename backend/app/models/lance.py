"""Somente lances aceitos; recusas ficam em TentativaLance."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, Index, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.leilao import Leilao
    from app.models.tentativa_lance import TentativaLance
    from app.models.usuario import Usuario


class Lance(Base):
    __tablename__ = "lances"
    __table_args__ = (
        CheckConstraint("valor > 0", name="ck_lances_valor"),
        Index("ix_lances_leilao_criado_em_id", "leilao_id", "criado_em", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    leilao_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("leiloes.id", ondelete="RESTRICT"), nullable=False
    )
    usuario_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    leilao: Mapped["Leilao"] = relationship(back_populates="lances", foreign_keys=[leilao_id])
    usuario: Mapped["Usuario"] = relationship()
    tentativa: Mapped["TentativaLance | None"] = relationship(
        back_populates="lance", passive_deletes="all", uselist=False
    )
