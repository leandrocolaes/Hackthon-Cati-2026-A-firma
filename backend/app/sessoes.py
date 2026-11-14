"""Quem esta logado: dependencias usadas pelas rotas (RF02, docs/autenticacao.md).

- usuario_atual: exige sessao valida e RENOVA o prazo. Para acoes humanas (POST).
- usuario_atual_sem_renovar: exige sessao valida e NAO renova. Para leituras que a
  tela faz sozinha (polling da sala), que nao podem impedir a expiracao por
  inatividade humana.

DECISAO: renova quem age (POST/DELETE), nao quem so le (GET). Para mudar, troque a
dependencia usada na rota.
"""

from dataclasses import dataclass
from datetime import timedelta

from fastapi import Depends, Request
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import obter_configuracoes
from app.db import get_db
from app.erros import ErroApi
from app.models import Sessao, Usuario
from app.seguranca import hash_token
from app.tempo import agora


@dataclass(frozen=True)
class UsuarioLogado:
    id: int
    nome: str
    email: str
    sessao_id: int  # o lance reconfere a sessao depois de esperar a trava (F08)


SESSAO_INVALIDA = ErroApi(401, "sessao_invalida", "Sessão inválida ou expirada. Entre novamente.")


def carregar(request: Request, db: Session, renovar: bool) -> UsuarioLogado | None:
    config = obter_configuracoes()
    token = request.cookies.get(config.sessao_cookie_nome)
    if not token:
        return None
    instante = agora(db)
    linha = db.execute(
        select(Sessao.id, Usuario.id, Usuario.nome, Usuario.email)
        .join(Usuario, Usuario.id == Sessao.usuario_id)
        .where(Sessao.token_hash == hash_token(token), Sessao.expira_em > instante)
    ).first()
    if linha is None:
        return None
    sessao_id, usuario_id, nome, email = linha
    if renovar:
        db.execute(update(Sessao).where(Sessao.id == sessao_id).values(
            expira_em=instante + timedelta(minutes=config.sessao_inatividade_minutos)))
        db.commit()
    return UsuarioLogado(id=usuario_id, nome=nome, email=email, sessao_id=sessao_id)


def usuario_atual(request: Request, db: Session = Depends(get_db)) -> UsuarioLogado:
    usuario = carregar(request, db, renovar=True)
    if usuario is None:
        raise SESSAO_INVALIDA
    return usuario


def usuario_atual_sem_renovar(request: Request, db: Session = Depends(get_db)) -> UsuarioLogado:
    usuario = carregar(request, db, renovar=False)
    if usuario is None:
        raise SESSAO_INVALIDA
    return usuario
