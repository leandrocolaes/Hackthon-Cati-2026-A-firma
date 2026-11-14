"""Edicao de leilao agendado e lista "meus leiloes" do comitente.

Edicao (RF23): so o comitente, so leilao Agendado, antes do inicio e sem lances.
Mesmos campos e limites da criacao; a lista de fotos substitui a anterior. O
formulario envia a versao lida ao abrir; se o leilao mudou nesse meio tempo, a
gravacao e recusada com 409 conflito_de_versao para o comitente revisar.

Quem esta na sala ve a mudanca sozinho: a edicao incrementa leiloes.versao, e a
tarefa de tempo real envia o snapshot novo (a tela recarrega o detalhe ao notar
versao nova com o leilao ainda agendado).

Usa a mesma trava do lance, da entrada na sala, da abertura e do cancelamento:
uma entrada na sala ou a abertura simultanea nunca "escapam" da regra.
"""

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app import dinheiro
from app.config import Configuracoes
from app.erros import ErroApi
from app.models import FotoItem, Item, Lance, Leilao, Participante
from app.regras import cancelamento_permitido, edicao_permitida
from app.schemas.leiloes import LeilaoEditar
from app.servicos.leiloes import gravar_fotos, nao_encontrado, validar
from app.tempo import agora, iso_utc


def _tem_lances(db: Session, leilao_id: int) -> bool:
    return db.execute(select(func.count()).select_from(Lance).where(
        Lance.leilao_id == leilao_id)).scalar_one() > 0


def editar(db: Session, cfg: Configuracoes, leilao_id: int, usuario_id: int, dados: LeilaoEditar) -> dict:
    leilao = db.execute(select(Leilao).where(Leilao.id == leilao_id).with_for_update()).scalar_one_or_none()
    if leilao is None:
        db.rollback()
        raise nao_encontrado()
    if leilao.comitente_id != usuario_id:
        db.rollback()
        raise ErroApi(403, "edicao_nao_autorizada", "Só o comitente pode editar este leilão.")
    if dados.versao != leilao.versao:
        db.rollback()
        raise ErroApi(
            409, "conflito_de_versao",
            "Este leilão foi alterado desde que o formulário foi aberto. Revise os dados antes de salvar.",
            {"versao_atual": leilao.versao},
        )
    instante = agora(db)  # depois da trava
    if not edicao_permitida(leilao.estado, instante, leilao.inicio, _tem_lances(db, leilao.id)):
        db.rollback()
        raise ErroApi(409, "edicao_nao_permitida",
                      "Só é possível editar um leilão agendado, antes do início e sem lances.")
    try:
        v = validar(db, cfg, usuario_id, dados)
    except ErroApi:
        db.rollback()
        raise
    db.execute(update(Item).where(Item.id == leilao.item_id)
               .values(nome=v.nome, descricao=v.descricao, categoria=dados.categoria))
    db.execute(delete(FotoItem).where(FotoItem.item_id == leilao.item_id))
    gravar_fotos(db, leilao.item_id, v.fotos)
    versao = db.execute(update(Leilao).where(Leilao.id == leilao_id).values(
        preco_inicial=v.preco, preco_atual=v.preco, inicio=dados.inicio,
        termino_original=v.termino, termino_vigente=v.termino, versao=Leilao.versao + 1,
    ).returning(Leilao.versao)).scalar_one()
    db.commit()
    return {"id": leilao_id, "item_id": leilao.item_id, "estado": "agendado", "versao": versao}


def meus(db: Session, usuario_id: int) -> dict:
    """Todos os leiloes do comitente (qualquer estado), mais recentes primeiro.
    DECISAO: sem paginacao; um usuario de demonstracao tem poucos leiloes."""
    capa = (select(FotoItem.url).where(FotoItem.item_id == Item.id)
            .order_by(FotoItem.ordem).limit(1).scalar_subquery())
    lances = (select(func.count()).select_from(Lance).where(Lance.leilao_id == Leilao.id).scalar_subquery())
    outros = (select(func.count()).select_from(Participante).where(
        Participante.leilao_id == Leilao.id, Participante.usuario_id != Leilao.comitente_id).scalar_subquery())
    linhas = db.execute(
        select(Leilao, Item.nome, Item.categoria, capa.label("capa"), lances.label("lances"),
               outros.label("outros"))
        .join(Item, Item.id == Leilao.item_id)
        .where(Leilao.comitente_id == usuario_id)
        .order_by(Leilao.id.desc())
    ).all()
    instante = agora(db)
    return {"itens": [{
        "id": l.id, "nome": nome, "categoria": categoria, "foto_principal": capa_url, "estado": l.estado,
        "preco_inicial": dinheiro.texto(l.preco_inicial), "preco_atual": dinheiro.texto(l.preco_atual),
        "inicio": iso_utc(l.inicio), "termino_vigente": iso_utc(l.termino_vigente),
        "total_lances": n_lances, "participantes": n_outros,
        "pode_editar": edicao_permitida(l.estado, instante, l.inicio, n_lances > 0),
        "pode_cancelar": cancelamento_permitido(l.estado, instante, l.termino_vigente, l.lider_id is not None),
    } for l, nome, categoria, capa_url, n_lances, n_outros in linhas]}
