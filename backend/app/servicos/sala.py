"""Snapshot da sala (RF09; docs/contratos.md, "Sala - exemplo de resposta/snapshot").

E personalizado (meu_participante_id, pode_dar_lance): nao compartilhar o mesmo
snapshot entre usuarios diferentes. Exige participacao: sem ela, 403 participante_ausente.

snapshot_publico (RF25, modo espectador): sem login e sem participacao, so leilao em
andamento, sem nenhum identificador interno nem dado pessoal; igual para todos.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import dinheiro
from app.config import Configuracoes
from app.erros import ErroApi
from app.models import Lance, Leilao, Participante
from app.regras import hard_end, impedimento, lance_minimo, prorrogacao_esgotada
from app.servicos.leiloes import nao_encontrado
from app.servicos.participantes import apelido
from app.tempo import agora, iso_utc

ULTIMOS_LANCES = 10  # contrato: dez lances mais recentes


def _lances(db: Session, leilao: Leilao):
    recentes = db.execute(
        select(Lance.id, Lance.usuario_id, Lance.valor, Lance.criado_em)
        .where(Lance.leilao_id == leilao.id)
        .order_by(Lance.criado_em.desc(), Lance.id.desc()).limit(ULTIMOS_LANCES)
    ).all()
    total = db.execute(select(func.count()).select_from(Lance).where(Lance.leilao_id == leilao.id)).scalar_one()
    vencedor = None
    if leilao.estado == "vendido" and leilao.lance_vencedor_id:
        vencedor = db.execute(select(Lance.usuario_id, Lance.valor)
                              .where(Lance.id == leilao.lance_vencedor_id)).one()
    return recentes, total, vencedor


def _prazos(leilao: Leilao, instante, cfg: Configuracoes) -> dict:
    return {
        "id": leilao.id, "versao": leilao.versao, "estado": leilao.estado, "server_time": iso_utc(instante),
        "inicio": iso_utc(leilao.inicio), "termino_original": iso_utc(leilao.termino_original),
        "termino_vigente": iso_utc(leilao.termino_vigente),
        # RF15 (fase 2): a sala mostra ate quando pode prorrogar e avisa quando chegou ao teto.
        "hard_end": iso_utc(hard_end(leilao.termino_original, cfg)),
        "prorrogacao_esgotada": prorrogacao_esgotada(leilao.termino_vigente, leilao.termino_original, cfg),
        "preco_atual": dinheiro.texto(leilao.preco_atual),
        "lance_minimo": dinheiro.texto(lance_minimo(leilao.preco_inicial, leilao.preco_atual,
                                                    leilao.lider_id is not None)),
    }


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
    recentes, total, vencedor = _lances(db, leilao)
    resultado = None
    if vencedor:
        resultado = {"vencedor": quem(vencedor.usuario_id), "valor": dinheiro.texto(vencedor.valor)}

    motivo = impedimento(leilao.estado, instante, leilao.termino_vigente,
                         usuario_id, leilao.comitente_id, leilao.lider_id)
    return {
        **_prazos(leilao, instante, cfg),
        "lider": quem(leilao.lider_id) if leilao.lider_id else None,
        "total_lances": total,
        "ultimos_lances": [{"id": i, **quem(u), "valor": dinheiro.texto(v), "criado_em": iso_utc(c)}
                           for i, u, v, c in recentes],
        "resultado": resultado,
        "meu_participante_id": meu,
        # Para a tela mostrar o cancelamento so ao comitente; quem decide e o servidor (RF08).
        "sou_comitente": usuario_id == leilao.comitente_id,
        "pode_dar_lance": motivo is None,
        "motivo_impedimento": motivo,
    }


def snapshot_publico(db: Session, cfg: Configuracoes, leilao_id: int, exigir_em_andamento: bool = True) -> dict:
    """RF25: o que o espectador ve (sem login e sem virar participante).

    Mesmo estado da sala, mas so com apelidos ("Participante N"): sem participante_id,
    id de lance, id de usuario, nome, e-mail, nem campos pessoais (meu_participante_id,
    sou_comitente, pode_dar_lance). Igual para todos: pode ser compartilhado.
    Entrar so em leilao em andamento (exigir_em_andamento); quem ja assiste pelo WS
    continua recebendo ate o resultado final.
    """
    leilao = db.execute(select(Leilao).where(Leilao.id == leilao_id)).scalar_one_or_none()
    if leilao is None:
        raise nao_encontrado()
    if exigir_em_andamento and leilao.estado != "em_andamento":
        raise ErroApi(409, "leilao_fora_do_estado", "Só dá para assistir a leilões em andamento.")
    numeros = dict(db.execute(select(Participante.usuario_id, Participante.numero)
                              .where(Participante.leilao_id == leilao_id)).all())

    def quem(uid):
        return {"apelido": apelido(numeros[uid])} if uid in numeros else None

    instante = agora(db)
    recentes, total, vencedor = _lances(db, leilao)
    return {
        **_prazos(leilao, instante, cfg),
        "lider": quem(leilao.lider_id) if leilao.lider_id else None,
        "total_lances": total,
        "ultimos_lances": [{**quem(u), "valor": dinheiro.texto(v), "criado_em": iso_utc(c)}
                           for _, u, v, c in recentes],
        "resultado": ({"vencedor": quem(vencedor.usuario_id), "valor": dinheiro.texto(vencedor.valor)}
                      if vencedor else None),
        "espectador": True,
    }
