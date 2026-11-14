"""Perfil publico do comitente (RF22).

GET /api/comitentes/{ref}: nome de exibicao, leiloes ativos (agendados e em andamento)
e resumo publico dos encerrados. A URL usa usuarios.ref_publica, nunca o id interno.

Nunca sai daqui: e-mail, ids de usuario, sessoes, dados de login, lances, vencedores
ou valores finais. DECISAO (resumo publico): contagem por estado final + os
RECENTES_ENCERRADOS ultimos encerrados (nome, categoria, estado e data), sem valor.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import dinheiro
from app.erros import ErroApi
from app.models import FotoItem, Item, Leilao, Usuario
from app.servicos.leiloes import ESTADOS_DO_CATALOGO, ordem_catalogo
from app.tempo import iso_utc

ESTADOS_FINAIS = ("vendido", "encerrado_sem_lances", "cancelado")
RECENTES_ENCERRADOS = 10


def _capa():
    return (select(FotoItem.url).where(FotoItem.item_id == Item.id)
            .order_by(FotoItem.ordem).limit(1).scalar_subquery())


def perfil(db: Session, ref: str) -> dict:
    linha = db.execute(select(Usuario.id, Usuario.nome, Usuario.ref_publica)
                       .where(Usuario.ref_publica == ref)).first()
    if linha is None:
        raise ErroApi(404, "recurso_nao_encontrado", "Comitente não encontrado.")
    usuario_id, nome, ref_publica = linha

    ativos = db.execute(
        select(Leilao, Item.nome, Item.categoria, _capa().label("capa"))
        .join(Item, Item.id == Leilao.item_id)
        .where(Leilao.comitente_id == usuario_id, Leilao.estado.in_(ESTADOS_DO_CATALOGO))
        .order_by(*ordem_catalogo("padrao"))
    ).all()

    contagem = dict(db.execute(
        select(Leilao.estado, func.count()).where(
            Leilao.comitente_id == usuario_id, Leilao.estado.in_(ESTADOS_FINAIS))
        .group_by(Leilao.estado)
    ).all())
    recentes = db.execute(
        select(Leilao.id, Leilao.estado, Leilao.encerrado_em, Item.nome, Item.categoria, _capa().label("capa"))
        .join(Item, Item.id == Leilao.item_id)
        .where(Leilao.comitente_id == usuario_id, Leilao.estado.in_(ESTADOS_FINAIS))
        .order_by(Leilao.encerrado_em.desc(), Leilao.id.desc())
        .limit(RECENTES_ENCERRADOS)
    ).all()

    return {
        "ref": ref_publica,
        "nome": nome,
        # Mesmo formato dos cartoes do catalogo (a tela reaproveita o CartaoLeilao).
        "ativos": [{
            "id": l.id, "nome": n, "categoria": c, "foto_principal": capa,
            "preco_atual": dinheiro.texto(l.preco_atual), "estado": l.estado,
            "inicio": iso_utc(l.inicio), "termino_vigente": iso_utc(l.termino_vigente),
        } for l, n, c, capa in ativos],
        "encerrados": {
            "vendidos": contagem.get("vendido", 0),
            "sem_lances": contagem.get("encerrado_sem_lances", 0),
            "cancelados": contagem.get("cancelado", 0),
            "recentes": [{
                "id": i, "nome": n, "categoria": c, "foto_principal": capa, "estado": e,
                "encerrado_em": iso_utc(fim),
            } for i, e, fim, n, c, capa in recentes],
        },
    }
