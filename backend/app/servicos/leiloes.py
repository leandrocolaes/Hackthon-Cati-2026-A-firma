"""Criacao, catalogo e detalhe de leiloes (RF05, RF06, RF07, RF20, RF21)."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from math import ceil
import unicodedata

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

# RF21: ordenacoes aceitas em ?ordenar= (o padrao e o do RF20).
ORDENACOES = ("padrao", "termina", "comeca", "preco_asc", "preco_desc")

# RF21. DECISAO: a busca e a categoria ignoram maiusculas E acentos ("relogio" acha
# "Relógio"; "Colecionaveis" acha "Colecionáveis"), sem depender da extensao unaccent:
# o banco troca as letras acentuadas com translate().
_COM_ACENTO = "ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑáàâãäéèêëíìîïóòôõöúùûüçñ"
_SEM_ACENTO = "AAAAAEEEEIIIIOOOOOUUUUCNaaaaaeeeeiiiiooooouuuucn"


def sem_acento(texto: str) -> str:
    """Mesma normalizacao que o banco aplica (minusculas, sem acentos)."""
    decomposto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c)).lower()


def _sem_acento_sql(coluna):
    return func.lower(func.translate(coluna, _COM_ACENTO, _SEM_ACENTO))


def ordem_catalogo(ordenar: str) -> tuple:
    """RF20/RF21. Desempate sempre por id: a paginacao nao repete nem pula itens."""
    if ordenar == "termina":
        return (Leilao.termino_vigente.asc(), Leilao.id)
    if ordenar == "comeca":
        return (Leilao.inicio.asc(), Leilao.id)
    if ordenar == "preco_asc":
        return (Leilao.preco_atual.asc(), Leilao.id)
    if ordenar == "preco_desc":
        return (Leilao.preco_atual.desc(), Leilao.id)
    if ordenar != "padrao":
        raise invalido("ordenar", "Ordenação inválida.")
    # padrao (RF20): em andamento pelo termino mais proximo, depois agendados pelo inicio.
    return (
        case((Leilao.estado == "em_andamento", 0), else_=1),
        case((Leilao.estado == "em_andamento", Leilao.termino_vigente), else_=Leilao.inicio),
        Leilao.id,
    )


def invalido(campo: str, motivo: str) -> ErroApi:
    """422 no mesmo formato da validacao automatica do FastAPI."""
    return ErroApi(422, "entrada_invalida", "Confira os campos informados.",
                   {"campos": [{"campo": campo, "motivo": motivo}]})


def nao_encontrado() -> ErroApi:
    return ErroApi(404, "recurso_nao_encontrado", "Leilão não encontrado.")


@dataclass(frozen=True)
class Validado:
    nome: str
    descricao: str
    preco: Decimal
    fotos: list[fotos.FotoResolvida]
    termino: datetime


def validar(db: Session, cfg: Configuracoes, comitente_id: int, dados: LeilaoCriar) -> Validado:
    """Regras de criacao, reaproveitadas pela edicao (mesmos limites, mesmos 422)."""
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
    return Validado(nome, descricao, preco, resolvidas, dados.inicio + timedelta(seconds=dados.duracao_segundos))


def gravar_fotos(db: Session, item_id: int, resolvidas: list[fotos.FotoResolvida]) -> None:
    for ordem, foto in enumerate(resolvidas):
        db.execute(insert(FotoItem).values(item_id=item_id, url=foto.url,
                                           chave_armazenamento=foto.chave_armazenamento, ordem=ordem))


def criar(db: Session, cfg: Configuracoes, comitente_id: int, dados: LeilaoCriar) -> LeilaoCriado:
    v = validar(db, cfg, comitente_id, dados)
    nome, descricao, preco, termino = v.nome, v.descricao, v.preco, v.termino
    try:
        item_id = db.execute(insert(Item).values(
            usuario_id=comitente_id, nome=nome, descricao=descricao, categoria=dados.categoria,
        ).returning(Item.id)).scalar_one()
        gravar_fotos(db, item_id, v.fotos)
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


def _preco_do_filtro(valor: str | None, campo: str) -> Decimal | None:
    """Converte um limite de preco da URL; vazio significa "sem limite"."""
    if valor is None or valor.strip() == "":
        return None
    try:
        numero = Decimal(valor.strip())
    except InvalidOperation:
        raise invalido(campo, "Preço inválido.") from None
    if not numero.is_finite() or numero < 0 or numero > dinheiro.MAXIMO:
        raise invalido(campo, "Preço inválido.")
    if numero != numero.quantize(dinheiro.CENTAVO):
        raise invalido(campo, "Use no máximo duas casas decimais.")
    return numero.quantize(dinheiro.CENTAVO)


def catalogo(
    db: Session,
    pagina: int,
    por_pagina: int,
    *,
    busca: str | None = None,
    categoria: str | None = None,
    estado: str | None = None,
    preco_min: str | None = None,
    preco_max: str | None = None,
    ordenar: str = "padrao",
) -> Catalogo:
    """RF20/RF21: so agendados e em andamento, com busca, filtros e ordenacao.

    O preco filtrado e sempre ``preco_atual``: nos agendados ele e igual ao
    preco inicial, e nos em andamento e o ultimo lance confirmado. A paginacao
    e feita no banco depois dos filtros, para o total refletir a consulta.
    """
    filtros = [Leilao.estado.in_(ESTADOS_DO_CATALOGO)]

    termo = (busca or "").strip()
    if termo:
        # So o nome. contains(..., autoescape) procura o texto literal (% e _ nao sao curingas).
        filtros.append(_sem_acento_sql(Item.nome).contains(sem_acento(termo), autoescape=True))

    nome_categoria = (categoria or "").strip()
    if nome_categoria:
        filtros.append(_sem_acento_sql(Item.categoria) == sem_acento(nome_categoria))

    if estado:
        filtros.append(Leilao.estado == estado)

    minimo = _preco_do_filtro(preco_min, "preco_min")
    maximo = _preco_do_filtro(preco_max, "preco_max")
    if minimo is not None and maximo is not None and minimo > maximo:
        raise invalido("preco_min", "O preço mínimo não pode ser maior que o máximo.")
    if minimo is not None:
        filtros.append(Leilao.preco_atual >= minimo)
    if maximo is not None:
        filtros.append(Leilao.preco_atual <= maximo)

    ordem = ordem_catalogo(ordenar)

    total = db.execute(
        select(func.count()).select_from(Leilao).join(Item, Item.id == Leilao.item_id).where(*filtros)
    ).scalar_one()
    linhas = db.execute(
        select(Leilao, Item.nome, Item.categoria, _foto_principal().label("foto"))
        .join(Item, Item.id == Leilao.item_id)
        .where(*filtros)
        .order_by(*ordem)
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
        inicio=iso_utc(l.inicio), termino_vigente=iso_utc(l.termino_vigente), versao=l.versao,
    )
