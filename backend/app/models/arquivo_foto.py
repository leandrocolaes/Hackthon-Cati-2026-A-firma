"""Bytes das fotos enviadas (RF07): guardadas no PostgreSQL.

DECISAO: o requisito de nuvem caiu; guardar no banco evita volume novo no compose
(deploy igual) e as fotos sobrevivem a reinicios junto com o volume do banco.
A foto existe antes do leilao: o upload devolve uma referencia opaca que so o
dono pode usar ao criar o leilao (fotos_itens guarda a URL publica e a referencia).
"""

from datetime import datetime

from sqlalchemy import (BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, Integer, LargeBinary,
                        String, func)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ArquivoFoto(Base):
    __tablename__ = "arquivos_fotos"
    __table_args__ = (CheckConstraint("tamanho > 0", name="ck_arquivos_fotos_tamanho"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    referencia: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    usuario_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    tipo: Mapped[str] = mapped_column(String, nullable=False)
    tamanho: Mapped[int] = mapped_column(Integer, nullable=False)
    dados: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
