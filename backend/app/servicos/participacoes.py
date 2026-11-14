"""Minhas participacoes (RF27): leiloes em que o usuario entrou como participante.

Quatro grupos (DECISAO para o que o documento deixa em aberto):
  em_disputa             agendado, em_andamento
  vencidos               vendido com o lance vencedor do usuario
  nao_vencidos           vendido para outro participante; encerrado_sem_lances
  cancelados_encerrados  cancelado (e qualquer outro final que nao caiba acima)
Leiloes em que o usuario e o comitente nao entram (ele os ve em "Meus leiloes").
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import dinheiro
from app.models import FotoItem, Item, Lance, Leilao, Participante
from app.servicos.leiloes import ESTADOS_DO_CATALOGO, ordem_catalogo
from app.tempo import iso_utc

GRUPOS = ("em_disputa", "vencidos", "nao_vencidos", "cancelados_encerrados")


def _grupo(estado: str, vencedor_id: int | None, usuario_id: int) -> str:
    if estado in ESTADOS_DO_CATALOGO:
        return "em_disputa"
    if estado == "vendido":
        return "vencidos" if vencedor_id == usuario_id else "nao_vencidos"
    if estado == "encerrado_sem_lances":
        return "nao_vencidos"
    return "cancelados_encerrados"


def minhas(db: Session, usuario_id: int) -> dict:
    capa = (select(FotoItem.url).where(FotoItem.item_id == Item.id)
            .order_by(FotoItem.ordem).limit(1).scalar_subquery())
    vencedor = select(Lance.usuario_id).where(Lance.id == Leilao.lance_vencedor_id).scalar_subquery()
    linhas = db.execute(
        select(Leilao, Item.nome, Item.categoria, capa.label("capa"), vencedor.label("vencedor"))
        .join(Item, Item.id == Leilao.item_id)
        .join(Participante, (Participante.leilao_id == Leilao.id) & (Participante.usuario_id == usuario_id))
        .where(Leilao.comitente_id != usuario_id)
        # Ativos na ordem do catalogo; finalizados do mais recente para o mais antigo.
        .order_by(Leilao.encerrado_em.desc().nulls_first(), *ordem_catalogo("padrao"))
    ).all()
    grupos: dict[str, list] = {g: [] for g in GRUPOS}
    for l, nome, categoria, foto, vencedor_id in linhas:
        grupos[_grupo(l.estado, vencedor_id, usuario_id)].append({
            "id": l.id, "nome": nome, "categoria": categoria, "foto_principal": foto, "estado": l.estado,
            # Preco atual (em disputa) ou final (encerrado): o confirmado no servidor.
            "preco": dinheiro.texto(l.preco_atual),
            "termino": iso_utc(l.encerrado_em or l.termino_vigente),
            "sala_acessivel": l.estado in ESTADOS_DO_CATALOGO,
        })
    return grupos
