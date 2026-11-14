"""Cada login possui token e prazo independentes das demais sessoes."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.usuario import Usuario


class Sessao(Base):
    __tablename__ = "sessoes"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("usuarios.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    # SHA-256 em hexadecimal (64 caracteres), nunca o token original nem bcrypt.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expira_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    usuario: Mapped["Usuario"] = relationship(back_populates="sessoes")
