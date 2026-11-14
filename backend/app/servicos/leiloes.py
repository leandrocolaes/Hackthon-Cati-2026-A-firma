"""Criacao, catalogo e detalhe de leiloes (RF05, RF06, RF07, RF20)."""

from datetime import timedelta
from math import ceil

from sqlalchemy import case, func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import dinheiro, fotos
from app.config import Configuracoes
from app.erros import ErroApi
from app.models import FotoItem, Item, Leilao
from app.schemas.leiloes import (Catalogo, FotoSaida, ItemSaida, LeilaoCartao, LeilaoCriado, LeilaoCriar,
                                 LeilaoDetalhe)
from app.tempo import agora, iso_utc

ESTADOS_DO_CATALOGO = ("agendado", "em_andamento")


def invalido(campo: str, motivo: str) -> ErroApi:
    """422 no mesmo formato da validacao automatica do FastAPI."""
    return ErroApi(422, "entrada_invalida", "Confira os campos informados.",
                   {"campos": [{"campo": campo, "motivo": motivo}]})


def nao_encontrado() -> ErroApi:
    return ErroApi(404, "recurso_nao_encontrado", "Leilão não encontrado.")


def criar(db: Session, cfg: Configuracoes, comitente_id: int, dados: LeilaoCriar) -> LeilaoCriado:
    nome, descricao = dados.nome.strip(), dados.descricao.strip()
    if not cfg.nome_item_minimo <= len(nome) <= cfg.nome_item_maximo:
        raise invalido("nome", f"Use de {cfg.nome_item_minimo} a {cfg.nome_item_maximo} caracteres.")
    if not cfg.descricao_item_minima <= len(descricao) <= cfg.descricao_item_maxima:
        raise invalido("descricao", f"Use de {cfg.descricao_item_minima} a {cfg.descricao_item_maxima} caracteres.")
    if dados.categoria not in cfg.categorias:
        raise invalido("categoria", "Escolha uma das categorias disponíveis.")
    preco = dinheiro.ler(dados.preco_inicial)
    if preco < cfg.preco_inicial_minimo:
        raise invalido("preco_inicial", f"O mínimo é {dinheiro.texto(cfg.preco_inicial_minimo)}.")

    # Antecedencia medida pelo relogio do banco, nao pelo do navegador (RF16).
    antecedencia = (dados.inicio - agora(db)).total_seconds()
    if not cfg.antecedencia_minima_segundos <= antecedencia <= cfg.antecedencia_maxima_segundos:
        raise invalido("inicio", f"O início deve ficar entre {cfg.antecedencia_minima_segundos} s e "
                                 f"{cfg.antecedencia_maxima_segundos} s a partir de agora.")
    if not cfg.duracao_minima_segundos <= dados.duracao_segundos <= cfg.duracao_maxima_segundos:
        raise invalido("duracao_segundos", f"A duração deve ficar entre {cfg.duracao_minima_segundos} s e "
                                           f"{cfg.duracao_maxima_segundos} s.")
    if not cfg.fotos_minimas <= len(dados.fotos) <= cfg.fotos_maximas:
        raise invalido("fotos", f"Envie de {cfg.fotos_minimas} a {cfg.fotos_maximas} fotos.")
    if len(set(dados.fotos)) != len(dados.fotos):
        raise invalido("fotos", "A mesma foto foi enviada mais de uma vez.")
    try:
        resolvidas = fotos.resolver(db, comitente_id, dados.fotos)
    except fotos.ReferenciaInvalida as e:
        raise invalido(f"fotos.{e.posicao - 1}", "Foto não encontrada ou não pertence a você.")

    termino = dados.inicio + timedelta(seconds=dados.duracao_segundos)
    try:
        item_id = db.execute(insert(Item).values(
            usuario_id=comitente_id, nome=nome, descricao=descricao, categoria=dados.categoria,
        ).returning(Item.id)).scalar_one()
        for ordem, foto in enumerate(resolvidas):
            db.execute(insert(FotoItem).values(item_id=item_id, url=foto.url,
                                               chave_armazenamento=foto.chave_armazenamento, ordem=ordem))
        leilao_id = db.execute(insert(Leilao).values(
            item_id=item_id, comitente_id=comitente_id,  # comitente = dono do item (dominio, item 1)
            preco_inicial=preco, preco_atual=preco,
            inicio=dados.inicio, termino_original=termino, termino_vigente=termino,
        ).returning(Leilao.id)).scalar_one()
        db.commit()
    except IntegrityError:
        # Item novo a cada criacao: so aconteceria com relistagem (RF28), que ainda nao existe.
        db.rollback()
        raise ErroApi(409, "item_com_leilao_ativo", "Este item já tem um leilão agendado ou em andamento.")
    return LeilaoCriado(id=leilao_id, item_id=item_id, estado="agendado")


def _foto_principal():
    return (select(FotoItem.url).where(FotoItem.item_id == Item.id)
            .order_by(FotoItem.ordem).limit(1).scalar_subquery())


def catalogo(db: Session, pagina: int, por_pagina: int) -> Catalogo:
    """RF20 (docs/contratos.md, "Catalogo e acesso"): so agendados e em andamento; em
    andamento primeiro por termino_vigente, depois agendados por inicio; desempate por id."""
    filtro = Leilao.estado.in_(ESTADOS_DO_CATALOGO)
    total = db.execute(select(func.count()).select_from(Leilao).where(filtro)).scalar_one()
    linhas = db.execute(
        select(Leilao, Item.nome, Item.categoria, _foto_principal().label("foto"))
        .join(Item, Item.id == Leilao.item_id)
        .where(filtro)
        .order_by(
            case((Leilao.estado == "em_andamento", 0), else_=1),
            case((Leilao.estado == "em_andamento", Leilao.termino_vigente), else_=Leilao.inicio),
            Leilao.id,
        )
        .limit(por_pagina).offset((pagina - 1) * por_pagina)
    ).all()
    itens = [LeilaoCartao(
        id=l.id, nome=nome, categoria=categoria, foto_principal=foto, preco_atual=dinheiro.texto(l.preco_atual),
        estado=l.estado, inicio=iso_utc(l.inicio), termino_vigente=iso_utc(l.termino_vigente),
    ) for l, nome, categoria, foto in linhas]
    return Catalogo(itens=itens, pagina=pagina, por_pagina=por_pagina, total=total)


def detalhe(db: Session, leilao_id: int) -> LeilaoDetalhe:
    """Publico em qualquer estado, sem historico de lances, participantes ou vencedor."""
    linha = db.execute(select(Leilao, Item).join(Item, Item.id == Leilao.item_id)
                       .where(Leilao.id == leilao_id)).first()
    if linha is None:
        raise nao_encontrado()
    l, item = linha
    lista = db.execute(select(FotoItem.url, FotoItem.ordem).where(FotoItem.item_id == item.id)
                       .order_by(FotoItem.ordem)).all()
    return LeilaoDetalhe(
        id=l.id,
        item=ItemSaida(id=item.id, nome=item.nome, descricao=item.descricao, categoria=item.categoria,
                       fotos=[FotoSaida(url=u, ordem=o) for u, o in lista]),
        estado=l.estado, preco_inicial=dinheiro.texto(l.preco_inicial), preco_atual=dinheiro.texto(l.preco_atual),
        inicio=iso_utc(l.inicio), termino_vigente=iso_utc(l.termino_vigente),
    )
