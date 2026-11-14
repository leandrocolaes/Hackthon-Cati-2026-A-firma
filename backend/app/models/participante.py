"""Identidade estavel por usuario/leilao; nao representa conexao por aba."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.leilao import Leilao
    from app.models.usuario import Usuario


class Participante(Base):
    __tablename__ = "participantes"
    __table_args__ = (
        UniqueConstraint("leilao_id", "usuario_id", name="uq_participantes_leilao_usuario"),
        UniqueConstraint("leilao_id", "numero", name="uq_participantes_leilao_numero"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    leilao_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("leiloes.id", ondelete="RESTRICT"), nullable=False
    )
    usuario_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # RF26: quando recebeu o (unico) aviso de lance superado neste leilao; NULL = nunca.
    avisado_superado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    leilao: Mapped["Leilao"] = relationship(back_populates="participantes")
    usuario: Mapped["Usuario"] = relationship()
