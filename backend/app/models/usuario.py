"""Dados persistidos da conta; nunca serialize o modelo diretamente na API."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Identity, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.sessao import Sessao


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = (
        CheckConstraint(
            "email = lower(btrim(email))",
            name="ck_usuarios_email_normalizado",
        ),
        CheckConstraint(
            "nome = btrim(nome) AND char_length(nome) > 0",
            name="ck_usuarios_nome_valido",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    senha_hash: Mapped[str] = mapped_column(Text, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # A exclusao e decidida pelo banco; nao apagar nem desvincular sessoes implicitamente.
    sessoes: Mapped[list["Sessao"]] = relationship(
        back_populates="usuario", passive_deletes="all"
    )
