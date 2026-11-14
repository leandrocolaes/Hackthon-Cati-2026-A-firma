"""Cancelamento pelo comitente (RF08, RN01, HU09).

Pode: Agendado; ou Em andamento SEM lances e ainda antes do termino.
Nao pode: com lances, depois do termino, ou em estado final. O registro continua
existindo com estado "cancelado" (RF08: o cancelamento nao apaga nada).

Usa a mesma trava do lance e do fechamento: cancelamento e lance simultaneos nunca
deixam um leilao "cancelado com lance aceito". Quem chega depois ve o estado novo.
"""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.erros import ErroApi
from app.models import Leilao
from app.regras import cancelamento_permitido
from app.servicos.leiloes import nao_encontrado
from app.tempo import agora, iso_utc


def cancelar(db: Session, leilao_id: int, usuario_id: int) -> dict:
    leilao = db.execute(select(Leilao).where(Leilao.id == leilao_id).with_for_update()).scalar_one_or_none()
    if leilao is None:
        db.rollback()
        raise nao_encontrado()
    if leilao.comitente_id != usuario_id:
        db.rollback()
        raise ErroApi(403, "cancelamento_nao_autorizado", "Só o comitente pode cancelar este leilão.")
    instante = agora(db)  # depois da trava
    if not cancelamento_permitido(leilao.estado, instante, leilao.termino_vigente, leilao.lider_id is not None):
        db.rollback()
        mensagem = ("Leilão com lances não pode ser cancelado." if leilao.lider_id is not None
                    else "Este leilão não pode mais ser cancelado.")
        raise ErroApi(409, "cancelamento_nao_permitido", mensagem)
    versao = db.execute(update(Leilao).where(Leilao.id == leilao_id)
                        .values(estado="cancelado", encerrado_em=instante, versao=Leilao.versao + 1)
                        .returning(Leilao.versao)).scalar_one()
    db.commit()
    return {"id": leilao_id, "estado": "cancelado", "encerrado_em": iso_utc(instante), "versao": versao}
