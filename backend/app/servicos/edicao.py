"""Edicao de leilao agendado e lista "meus leiloes" do comitente.

Edicao (DECISAO da equipe): so o comitente, so leilao agendado e antes do inicio, e
so se ninguem alem dele entrou na sala OU se falta mais de 10 min para o inicio
(regras.edicao_permitida). Mesmos campos e limites da criacao; a lista de fotos
substitui a anterior. Preco, inicio e duracao novos valem do zero (sem lances ainda).

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
from app.schemas.leiloes import LeilaoCriar
from app.servicos.leiloes import gravar_fotos, nao_encontrado, validar
from app.tempo import agora, iso_utc


def _outros_participantes(db: Session, leilao: Leilao) -> int:
    return db.execute(select(func.count()).select_from(Participante).where(
        Participante.leilao_id == leilao.id, Participante.usuario_id != leilao.comitente_id)).scalar_one()


def editar(db: Session, cfg: Configuracoes, leilao_id: int, usuario_id: int, dados: LeilaoCriar) -> dict:
    leilao = db.execute(select(Leilao).where(Leilao.id == leilao_id).with_for_update()).scalar_one_or_none()
    if leilao is None:
        db.rollback()
        raise nao_encontrado()
    if leilao.comitente_id != usuario_id:
        db.rollback()
        raise ErroApi(403, "edicao_nao_autorizada", "Só o comitente pode editar este leilão.")
    instante = agora(db)  # depois da trava
    if not edicao_permitida(leilao.estado, instante, leilao.inicio, _outros_participantes(db, leilao), cfg):
        db.rollback()
        minutos = cfg.edicao_antecedencia_segundos // 60
        raise ErroApi(409, "edicao_nao_permitida",
                      "Só dá para editar leilão agendado: sem ninguém na sala ou com mais de "
                      f"{minutos} minutos até o início.")
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


def meus(db: Session, cfg: Configuracoes, usuario_id: int) -> dict:
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
        "pode_editar": edicao_permitida(l.estado, instante, l.inicio, n_outros, cfg),
        "pode_cancelar": cancelamento_permitido(l.estado, instante, l.termino_vigente, l.lider_id is not None),
    } for l, nome, categoria, capa_url, n_lances, n_outros in linhas]}
