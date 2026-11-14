"""Entradas e saidas de leiloes (docs/contratos.md). Dinheiro como texto; instantes em UTC."""

from pydantic import AwareDatetime, BaseModel, Field, field_validator

from app import dinheiro


class LeilaoCriar(BaseModel):
    nome: str = Field(max_length=500)
    descricao: str = Field(max_length=5000)
    categoria: str = Field(max_length=200)
    preco_inicial: str = Field(max_length=30)
    # AwareDatetime: instante sem fuso e recusado com 422 (nunca presumir fuso local).
    inicio: AwareDatetime
    duracao_segundos: int
    fotos: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("preco_inicial")
    @classmethod
    def _preco(cls, v: str) -> str:
        dinheiro.ler(v)  # ValueError vira 422 com o motivo
        return v.strip()


class LeilaoCriado(BaseModel):
    id: int
    item_id: int
    estado: str


class LeilaoCartao(BaseModel):
    id: int
    nome: str
    categoria: str
    foto_principal: str | None
    preco_atual: str
    estado: str
    inicio: str
    termino_vigente: str


class Catalogo(BaseModel):
    itens: list[LeilaoCartao]
    pagina: int
    por_pagina: int
    total: int


class FotoSaida(BaseModel):
    url: str
    ordem: int


class ItemSaida(BaseModel):
    id: int
    nome: str
    descricao: str
    categoria: str
    fotos: list[FotoSaida]


class LeilaoDetalhe(BaseModel):
    id: int
    item: ItemSaida
    estado: str
    preco_inicial: str
    preco_atual: str
    inicio: str
    termino_vigente: str


class ParticipanteSaida(BaseModel):
    id: int
    numero: int
    apelido: str
