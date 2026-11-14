"""Entrada na sala (RF10, condicao 1; docs/dominio.md, item 11).

"Estar na sala" = ter registro de Participante no leilao. O registro e estavel por
usuario e leilao (o mesmo nos varios aparelhos) e nao expira.
"""

from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from app.models import Leilao, Participante
from app.schemas.leiloes import ParticipanteSaida
from app.servicos.leiloes import nao_encontrado


def apelido(numero: int) -> str:
    """RF09. DECISAO: lider e lances aparecem como "Participante N", nunca pelo nome."""
    return f"Participante {numero}"


def entrar(db: Session, leilao_id: int, usuario_id: int) -> ParticipanteSaida:
    """Cria ou reaproveita a participacao. Idempotente.

    DECISAO: qualquer usuario logado entra em qualquer estado do leilao, inclusive o
    comitente (so assiste: o lance dele e recusado com lance_do_comitente) e leiloes
    encerrados (para ver o resultado na sala). Para restringir, recuse aqui.
    """
    # Trava o leilao: duas entradas simultaneas nao calculam o mesmo "max + 1".
    if db.execute(select(Leilao.id).where(Leilao.id == leilao_id).with_for_update()).scalar_one_or_none() is None:
        db.rollback()
        raise nao_encontrado()
    existente = db.execute(select(Participante.id, Participante.numero).where(
        Participante.leilao_id == leilao_id, Participante.usuario_id == usuario_id)).first()
    if existente:
        db.rollback()
        return ParticipanteSaida(id=existente.id, numero=existente.numero, apelido=apelido(existente.numero))
    numero = db.execute(select(func.coalesce(func.max(Participante.numero), 0) + 1)
                        .where(Participante.leilao_id == leilao_id)).scalar_one()
    participante_id = db.execute(insert(Participante).values(
        leilao_id=leilao_id, usuario_id=usuario_id, numero=numero).returning(Participante.id)).scalar_one()
    db.commit()  # criar participante nao incrementa a versao do leilao (contrato)
    return ParticipanteSaida(id=participante_id, numero=numero, apelido=apelido(numero))
