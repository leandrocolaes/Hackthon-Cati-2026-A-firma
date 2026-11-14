"""Somente referencias a fotos armazenadas no servico de nuvem."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.item import Item


class FotoItem(Base):
    __tablename__ = "fotos_itens"
    __table_args__ = (
        UniqueConstraint("item_id", "ordem", name="uq_fotos_itens_item_ordem"),
        CheckConstraint("ordem >= 0", name="ck_fotos_itens_ordem"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("itens.id", ondelete="RESTRICT"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    chave_armazenamento: Mapped[str | None] = mapped_column(Text, nullable=True)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    item: Mapped["Item"] = relationship(back_populates="fotos")
