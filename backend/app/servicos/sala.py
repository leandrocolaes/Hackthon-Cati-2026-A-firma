"""Snapshot da sala (RF09; docs/contratos.md, "Sala - exemplo de resposta/snapshot").

E personalizado (meu_participante_id, pode_dar_lance): nao compartilhar o mesmo
snapshot entre usuarios diferentes. Exige participacao: sem ela, 403 participante_ausente.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import dinheiro
from app.config import Configuracoes
from app.erros import ErroApi
from app.models import Lance, Leilao, Participante
from app.regras import impedimento, lance_minimo
from app.servicos.leiloes import nao_encontrado
from app.servicos.participantes import apelido
from app.tempo import agora, iso_utc

ULTIMOS_LANCES = 10  # contrato: dez lances mais recentes


def snapshot(db: Session, cfg: Configuracoes, leilao_id: int, usuario_id: int) -> dict:
    leilao = db.execute(select(Leilao).where(Leilao.id == leilao_id)).scalar_one_or_none()
    if leilao is None:
        raise nao_encontrado()
    participantes = dict(db.execute(select(Participante.usuario_id, Participante.id)
                                    .where(Participante.leilao_id == leilao_id)).all())
    numeros = dict(db.execute(select(Participante.id, Participante.numero)
                              .where(Participante.leilao_id == leilao_id)).all())
    meu = participantes.get(usuario_id)
    if meu is None:
        raise ErroApi(403, "participante_ausente", "Entre na sala do leilão para acompanhá-lo.")

    def quem(uid):
        pid = participantes.get(uid)
        return {"participante_id": pid, "apelido": apelido(numeros[pid])} if pid else None

    instante = agora(db)
    recentes = db.execute(
        select(Lance.id, Lance.usuario_id, Lance.valor, Lance.criado_em)
        .where(Lance.leilao_id == leilao_id)
        .order_by(Lance.criado_em.desc(), Lance.id.desc()).limit(ULTIMOS_LANCES)
    ).all()
    total = db.execute(select(func.count()).select_from(Lance).where(Lance.leilao_id == leilao_id)).scalar_one()

    resultado = None
    if leilao.estado == "vendido" and leilao.lance_vencedor_id:
        autor, valor = db.execute(select(Lance.usuario_id, Lance.valor)
                                  .where(Lance.id == leilao.lance_vencedor_id)).one()
        resultado = {"vencedor": quem(autor), "valor": dinheiro.texto(valor)}

    motivo = impedimento(leilao.estado, instante, leilao.termino_vigente,
                         usuario_id, leilao.comitente_id, leilao.lider_id)
    return {
        "id": leilao.id, "versao": leilao.versao, "estado": leilao.estado, "server_time": iso_utc(instante),
        "inicio": iso_utc(leilao.inicio), "termino_original": iso_utc(leilao.termino_original),
        "termino_vigente": iso_utc(leilao.termino_vigente),
        "preco_atual": dinheiro.texto(leilao.preco_atual),
        "lance_minimo": dinheiro.texto(lance_minimo(leilao.preco_inicial, leilao.preco_atual,
                                                    leilao.lider_id is not None, cfg)),
        "lider": quem(leilao.lider_id) if leilao.lider_id else None,
        "total_lances": total,
        "ultimos_lances": [{"id": i, **quem(u), "valor": dinheiro.texto(v), "criado_em": iso_utc(c)}
                           for i, u, v, c in recentes],
        "resultado": resultado,
        "meu_participante_id": meu,
        "pode_dar_lance": motivo is None,
        "motivo_impedimento": motivo,
    }
