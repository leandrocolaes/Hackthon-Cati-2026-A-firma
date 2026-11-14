"""Catalogo, detalhe, criacao e entrada na sala (docs/contratos.md).

    GET  /api/config-publica                  -> limites e categorias para o formulario
    POST /api/leiloes                         -> 201 {id, item_id, estado}
    GET  /api/leiloes?pagina=1&por_pagina=20  -> catalogo publico
    GET  /api/leiloes/{id}                    -> detalhe publico
    POST /api/leiloes/{id}/participantes      -> 200 {id, numero, apelido}
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import dinheiro
from app.config import Configuracoes, obter_configuracoes
from app.db import get_db
from app.schemas.leiloes import Catalogo, LeilaoCriado, LeilaoCriar, LeilaoDetalhe, ParticipanteSaida
from app.servicos import leiloes, participantes
from app.sessoes import UsuarioLogado, usuario_atual

router = APIRouter(prefix="/api", tags=["leilões"])


@router.get("/config-publica")
def config_publica(cfg: Configuracoes = Depends(obter_configuracoes)):
    """So esta selecao de limites; nunca serializar Configuracoes inteira (tem DATABASE_URL)."""
    return {
        "item": {"nome_minimo": cfg.nome_item_minimo, "nome_maximo": cfg.nome_item_maximo,
                 "descricao_minima": cfg.descricao_item_minima, "descricao_maxima": cfg.descricao_item_maxima,
                 "fotos_minimas": cfg.fotos_minimas, "fotos_maximas": cfg.fotos_maximas},
        "leilao": {"preco_inicial_minimo": dinheiro.texto(cfg.preco_inicial_minimo),
                   "antecedencia_minima_segundos": cfg.antecedencia_minima_segundos,
                   "antecedencia_maxima_segundos": cfg.antecedencia_maxima_segundos,
                   "duracao_minima_segundos": cfg.duracao_minima_segundos,
                   "duracao_maxima_segundos": cfg.duracao_maxima_segundos},
        "foto": {"maxima_bytes": cfg.foto_maxima_bytes, "tipos_permitidos": list(cfg.foto_tipos_permitidos)},
        "categorias": list(cfg.categorias),
    }


@router.post("/leiloes", status_code=201, response_model=LeilaoCriado)
def criar(dados: LeilaoCriar, usuario: UsuarioLogado = Depends(usuario_atual),
          cfg: Configuracoes = Depends(obter_configuracoes), db: Session = Depends(get_db)):
    """O comitente e o usuario da sessao; nunca um id enviado pela tela."""
    return leiloes.criar(db, cfg, usuario.id, dados)


@router.get("/leiloes", response_model=Catalogo)
def catalogo(pagina: int = Query(1, ge=1), por_pagina: int = Query(20, ge=1, le=100),
             db: Session = Depends(get_db)):
    """Fora da faixa da 422 (sem correcao silenciosa, conforme o contrato)."""
    return leiloes.catalogo(db, pagina, por_pagina)


@router.get("/leiloes/{leilao_id}", response_model=LeilaoDetalhe)
def detalhe(leilao_id: int, db: Session = Depends(get_db)):
    return leiloes.detalhe(db, leilao_id)


@router.post("/leiloes/{leilao_id}/participantes", response_model=ParticipanteSaida)
def entrar(leilao_id: int, usuario: UsuarioLogado = Depends(usuario_atual), db: Session = Depends(get_db)):
    return participantes.entrar(db, leilao_id, usuario.id)
