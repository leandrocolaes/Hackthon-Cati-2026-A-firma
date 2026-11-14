"""Resultado completo de uma tentativa, gravado atomicamente com seu efeito."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.lance import Lance
    from app.models.leilao import Leilao
    from app.models.usuario import Usuario


class TentativaLance(Base):
    __tablename__ = "tentativas_lance"
    __table_args__ = (
        UniqueConstraint("usuario_id", "chave", name="uq_tentativas_lance_usuario_chave"),
        UniqueConstraint("lance_id", name="uq_tentativas_lance_lance"),
        CheckConstraint("situacao IN ('aceita','recusada')", name="ck_tentativas_lance_situacao"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    leilao_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("leiloes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    chave: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    valor_solicitado: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    lance_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("lances.id", ondelete="RESTRICT"), nullable=True
    )
    situacao: Mapped[str] = mapped_column(String, nullable=False)
    status_http: Mapped[int] = mapped_column(Integer, nullable=False)
    resposta_original: Mapped[dict[str, Any]] = mapped_column(JSONB(none_as_null=True), nullable=False)

    usuario: Mapped["Usuario"] = relationship()
    leilao: Mapped["Leilao"] = relationship(back_populates="tentativas")
    lance: Mapped["Lance | None"] = relationship(back_populates="tentativa")
