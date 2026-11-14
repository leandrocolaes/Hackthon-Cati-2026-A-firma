"""Relogio oficial do sistema (RF16) e formato dos instantes na API (RF19).

agora(db): hora do PostgreSQL via clock_timestamp(). E a hora real no momento da
chamada; now() fica congelado no inicio da transacao e, depois de esperar uma trava
(lance, fechamento), estaria atrasado. Toda decisao de prazo usa agora(db), nunca o
relogio do Python nem o do navegador (docs/dominio.md, item 10).

iso_utc(instante): instante -> texto ISO-8601 em UTC terminado em "Z", o formato
das respostas (docs/contratos.md, "Convencoes").
"""

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session


def agora(db: Session) -> datetime:
    return db.execute(text("SELECT clock_timestamp()")).scalar_one()


def iso_utc(instante: datetime) -> str:
    if instante.tzinfo is None:
        # Instante sem fuso e ambiguo: e erro de programacao, nunca presumir fuso local.
        raise ValueError("instante sem fuso horario")
    return instante.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
