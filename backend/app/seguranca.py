"""Senhas (bcrypt) e tokens de sessao (aleatorio + SHA-256). Contrato: docs/autenticacao.md."""

import hashlib
import secrets

import bcrypt

SENHA_MIN_CARACTERES = 8
SENHA_MAX_BYTES = 72  # limite do bcrypt; validado antes para nunca truncar em silencio

# Hash valido de uma senha qualquer: usado quando o e-mail nao existe, para que o
# login demore o mesmo tanto e o tempo de resposta nao revele quais e-mails tem conta.
_HASH_FICTICIO = bcrypt.hashpw(b"senha-que-ninguem-usa", bcrypt.gensalt()).decode()


def validar_senha(senha: str) -> str | None:
    """Devolve o motivo da recusa, ou None se a senha e aceitavel. Nao altera a senha."""
    if len(senha) < SENHA_MIN_CARACTERES:
        return f"A senha precisa ter pelo menos {SENHA_MIN_CARACTERES} caracteres."
    if len(senha.encode("utf-8")) > SENHA_MAX_BYTES:
        return f"A senha pode ter no máximo {SENHA_MAX_BYTES} bytes (letras acentuadas ocupam 2)."
    return None


def gerar_hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode()


def conferir_senha(senha: str, senha_hash: str | None) -> bool:
    alvo = (senha_hash or _HASH_FICTICIO).encode()
    try:
        ok = bcrypt.checkpw(senha.encode("utf-8"), alvo)
    except ValueError:
        return False
    return ok and senha_hash is not None


def gerar_token() -> str:
    """Token entregue ao navegador no cookie. Nunca e gravado no banco nem em logs."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """O que vai para sessoes.token_hash: SHA-256 hex, deterministico (busca pelo indice)."""
    return hashlib.sha256(token.encode()).hexdigest()
