"""Entradas e saidas de usuario e sessao (docs/autenticacao.md, docs/contratos.md)."""

import re

from pydantic import BaseModel, Field, field_validator

from app.seguranca import validar_senha

# Checagem simples de formato (sem confirmacao por e-mail).
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalizar_email(valor: str) -> str:
    """Remove espacos nas pontas e converte para minusculas. Nao remove pontos nem '+'."""
    return valor.strip().lower()


class CadastroEntrada(BaseModel):
    nome: str = Field(max_length=300)
    email: str = Field(max_length=300)
    senha: str = Field(max_length=300)

    @field_validator("nome")
    @classmethod
    def _nome(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Informe o nome.")
        if len(v) > 100:
            raise ValueError("O nome pode ter no máximo 100 caracteres.")
        return v

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = normalizar_email(v)
        if len(v) > 254 or not _EMAIL.match(v):
            raise ValueError("Informe um e-mail válido.")
        return v

    @field_validator("senha")
    @classmethod
    def _senha(cls, v: str) -> str:
        motivo = validar_senha(v)  # a senha nunca e alterada (sem strip)
        if motivo:
            raise ValueError(motivo)
        return v


class LoginEntrada(BaseModel):
    email: str = Field(max_length=300)
    senha: str = Field(max_length=300)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return normalizar_email(v)


class UsuarioSaida(BaseModel):
    """O proprio usuario. Nunca inclui senha_hash. E-mail so aparece para o dono da conta."""
    id: int
    nome: str
    email: str


class SessaoSaida(BaseModel):
    usuario: UsuarioSaida
