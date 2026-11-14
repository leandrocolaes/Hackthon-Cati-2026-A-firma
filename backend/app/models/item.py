"""Bem anunciado; os leiloes reutilizam os dados do item, sem copia."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.foto_item import FotoItem
    from app.models.leilao import Leilao
    from app.models.usuario import Usuario


class Item(Base):
    __tablename__ = "itens"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    descricao: Mapped[str] = mapped_column(String(2000), nullable=False)
    categoria: Mapped[str] = mapped_column(String, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    usuario: Mapped["Usuario"] = relationship()
    fotos: Mapped[list["FotoItem"]] = relationship(
        back_populates="item", passive_deletes="all", order_by="FotoItem.ordem"
    )
    leiloes: Mapped[list["Leilao"]] = relationship(
        back_populates="item", passive_deletes="all"
    )
