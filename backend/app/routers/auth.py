"""Cadastro, login, logout e usuario atual (RF01, RF02, HU01, HU02).

Rotas e respostas conforme docs/contratos.md:
    POST   /api/usuarios  -> 201 {id, nome, email}
    POST   /api/sessao    -> 200 {usuario: {...}} + cookie HttpOnly
    DELETE /api/sessao    -> 204 (encerra so a sessao deste navegador)
    GET    /api/eu        -> 200 {id, nome, email} | 401 sessao_invalida
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import obter_configuracoes
from app.db import get_db
from app.erros import ErroApi
from app.models import Sessao, Usuario
from app.schemas.auth import CadastroEntrada, LoginEntrada, SessaoSaida, UsuarioSaida
from app.seguranca import conferir_senha, gerar_hash_senha, gerar_token, hash_token
from app.sessoes import UsuarioLogado, usuario_atual_sem_renovar
from app.tempo import agora

router = APIRouter(prefix="/api", tags=["usuários e sessão"])

# DECISAO: cookie sem a opcao Secure, porque a VM e acessada por HTTP. Com Secure e
# sem HTTPS o navegador descarta o cookie e o login "nao funciona". Se houver HTTPS
# (bonus), troque para True.
COOKIE_SEGURO = False


@router.post("/usuarios", status_code=201, response_model=UsuarioSaida)
def cadastrar(dados: CadastroEntrada, db: Session = Depends(get_db)):
    """DECISAO (contrato): o cadastro NAO abre sessao; a tela faz o login em seguida."""
    try:
        usuario_id = db.execute(
            insert(Usuario).values(nome=dados.nome, email=dados.email, senha_hash=gerar_hash_senha(dados.senha))
            .returning(Usuario.id)
        ).scalar_one()
        db.commit()
    except IntegrityError:
        # UNIQUE(email) no banco: protege inclusive contra dois cadastros simultaneos.
        db.rollback()
        raise ErroApi(409, "email_ja_cadastrado", "Este e-mail já está cadastrado.")
    return UsuarioSaida(id=usuario_id, nome=dados.nome, email=dados.email)


@router.post("/sessao", response_model=SessaoSaida)
def entrar(dados: LoginEntrada, response: Response, db: Session = Depends(get_db)):
    config = obter_configuracoes()
    linha = db.execute(
        select(Usuario.id, Usuario.nome, Usuario.email, Usuario.senha_hash).where(Usuario.email == dados.email)
    ).first()
    # Roda o bcrypt mesmo sem usuario: o tempo de resposta nao denuncia quais e-mails existem.
    if not conferir_senha(dados.senha, linha.senha_hash if linha else None):
        raise ErroApi(401, "credenciais_invalidas", "e-mail ou senha inválidos")

    instante = agora(db)
    # Limpeza oportunista (docs/autenticacao.md): sessoes vencidas ja eram invalidas.
    db.execute(delete(Sessao).where(Sessao.expira_em <= instante))
    token = gerar_token()
    db.execute(insert(Sessao).values(
        usuario_id=linha.id, token_hash=hash_token(token),
        expira_em=instante + timedelta(minutes=config.sessao_inatividade_minutos),
    ))
    db.commit()
    response.set_cookie(
        key=config.sessao_cookie_nome, value=token,
        httponly=True,      # o JavaScript nao le o cookie
        samesite="lax",
        secure=COOKIE_SEGURO,
        path="/",
        # Sem max_age: cookie de sessao do navegador. Quem decide a expiracao e o banco.
    )
    return SessaoSaida(usuario=UsuarioSaida(id=linha.id, nome=linha.nome, email=linha.email))


@router.delete("/sessao", status_code=204)
def sair(request: Request, response: Response, db: Session = Depends(get_db)):
    """Encerra so a sessao deste navegador; as dos outros aparelhos continuam."""
    config = obter_configuracoes()
    token = request.cookies.get(config.sessao_cookie_nome)
    if token:
        db.execute(delete(Sessao).where(Sessao.token_hash == hash_token(token)))
        db.commit()
    response.delete_cookie(config.sessao_cookie_nome, path="/")


@router.get("/eu", response_model=UsuarioSaida)
def eu(usuario: UsuarioLogado = Depends(usuario_atual_sem_renovar)):
    """Usuario desta sessao. GET nao renova a sessao (a tela chama ao abrir)."""
    return UsuarioSaida(id=usuario.id, nome=usuario.nome, email=usuario.email)
