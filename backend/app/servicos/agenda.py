"""Abertura e fechamento automaticos (RF17, RF18). Usado pelo worker (app/worker.py).

Tudo e decidido consultando o banco a cada volta, sem timers em memoria. Por isso
um reinicio nao perde nada: na primeira volta, o que venceu durante a parada e
corrigido. Rodar duas vezes (ou dois workers) nao duplica resultado: cada
transicao confere o estado atual antes de agir.

Cada transicao incrementa leiloes.versao na mesma transacao (docs/contratos.md,
"Versao e comunicacao worker/API"): e por ela que a API percebe a mudanca e
atualiza as salas.
"""

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.models import Lance, Leilao
from app.tempo import agora


def abrir_vencidos(db: Session) -> list[int]:
    """agendado -> em_andamento para todo leilao cujo inicio ja passou."""
    ids = db.execute(
        update(Leilao)
        .where(Leilao.estado == "agendado", Leilao.inicio <= text("clock_timestamp()"))
        .values(estado="em_andamento", versao=Leilao.versao + 1)
        .returning(Leilao.id)
    ).scalars().all()
    db.commit()
    return list(ids)


def fechar(db: Session, leilao_id: int) -> str | None:
    """Fecha UM leilao se ele de fato venceu. Devolve o estado final, ou None.

    Usa a MESMA trava do lance (SELECT ... FOR UPDATE na linha do leilao): fechamento
    e lance no mesmo leilao nunca se misturam (RF18: nunca ha fechamento no meio de
    um lance, nem lance aceito depois do fechamento).
    """
    leilao = db.execute(select(Leilao).where(Leilao.id == leilao_id).with_for_update()).scalar_one_or_none()
    instante = agora(db)  # lido DEPOIS da trava
    # Reconfere sob a trava: um lance pode ter prorrogado o termino enquanto esperavamos.
    if leilao is None or leilao.estado != "em_andamento" or leilao.termino_vigente > instante:
        db.rollback()
        return None
    vencedor_id = None
    if leilao.lider_id is not None:
        # Maior lance aceito; em empate (nao deveria haver), o mais antigo.
        vencedor_id = db.execute(
            select(Lance.id).where(Lance.leilao_id == leilao_id)
            .order_by(Lance.valor.desc(), Lance.id.asc()).limit(1)
        ).scalar_one()
    estado = "vendido" if vencedor_id else "encerrado_sem_lances"
    db.execute(update(Leilao).where(Leilao.id == leilao_id).values(
        estado=estado, lance_vencedor_id=vencedor_id,
        # DECISAO: encerrado_em = quando o sistema processou o fechamento. O termino
        # oficial continua sendo termino_vigente (podem diferir apos uma parada).
        encerrado_em=instante, versao=Leilao.versao + 1,
    ))
    db.commit()
    return estado


def fechar_vencidos(db: Session) -> dict[int, str]:
    candidatos = db.execute(
        select(Leilao.id).where(Leilao.estado == "em_andamento",
                                Leilao.termino_vigente <= text("clock_timestamp()"))
        .order_by(Leilao.termino_vigente)
    ).scalars().all()
    db.rollback()  # encerra a leitura antes de abrir uma transacao por leilao
    fechados = {}
    for leilao_id in candidatos:
        estado = fechar(db, leilao_id)
        if estado:
            fechados[leilao_id] = estado
    return fechados


def ciclo(db: Session) -> tuple[list[int], dict[int, str]]:
    """Uma volta do worker. Abre antes de fechar: um leilao que passou inteiro durante
    uma parada faz agendado -> em_andamento -> encerrado na mesma volta (so
    transicoes permitidas pelo RN01)."""
    return abrir_vencidos(db), fechar_vencidos(db)
