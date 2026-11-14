"""Configuracao validada uma vez por processo; ambiente tem prioridade sobre .env."""

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

ARQUIVO_ENV = Path(__file__).resolve().parents[2] / ".env"
ListaConfigurada = Annotated[tuple[str, ...], NoDecode]


class Configuracoes(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ARQUIVO_ENV,
        env_file_encoding="utf-8",
        extra="ignore",  # .env tambem possui variaveis exclusivas do Compose.
        frozen=True,
        hide_input_in_errors=True,
    )

    database_url: SecretStr = Field(validation_alias="DATABASE_URL", repr=False)
    sessao_inatividade_minutos: int = Field(120, gt=0, validation_alias="SESSION_IDLE_MINUTES")
    sessao_cookie_nome: str = Field("afirma_sessao", min_length=1, validation_alias="SESSION_COOKIE_NAME")
    incremento_centavos: int = Field(100, gt=0, validation_alias="BID_INCREMENT_CENTS")
    prorrogacao_janela_segundos: int = Field(60, gt=0, validation_alias="AUCTION_EXTENSION_WINDOW_SECONDS")
    prorrogacao_segundos: int = Field(60, gt=0, validation_alias="AUCTION_EXTENSION_SECONDS")
    prorrogacao_maxima_segundos: int = Field(600, gt=0, validation_alias="AUCTION_EXTENSION_MAX_SECONDS")
    preco_inicial_minimo: Decimal = Field(
        Decimal("1.00"), gt=0, max_digits=12, decimal_places=2,
        allow_inf_nan=False, validation_alias="AUCTION_MIN_START_PRICE",
    )
    antecedencia_minima_segundos: int = Field(60, gt=0, validation_alias="AUCTION_MIN_ADVANCE_SECONDS")
    antecedencia_maxima_segundos: int = Field(2592000, gt=0, validation_alias="AUCTION_MAX_ADVANCE_SECONDS")
    duracao_minima_segundos: int = Field(60, gt=0, validation_alias="AUCTION_MIN_DURATION_SECONDS")
    duracao_maxima_segundos: int = Field(604800, gt=0, validation_alias="AUCTION_MAX_DURATION_SECONDS")
    # Edicao: liberada se ninguem (alem do comitente) entrou na sala OU se falta mais que isto para o inicio.
    edicao_antecedencia_segundos: int = Field(600, ge=0, validation_alias="AUCTION_EDIT_MIN_ADVANCE_SECONDS")
    nome_item_minimo: int = Field(3, ge=1, le=100, validation_alias="ITEM_NAME_MIN_LENGTH")
    nome_item_maximo: int = Field(100, ge=1, le=100, validation_alias="ITEM_NAME_MAX_LENGTH")
    descricao_item_minima: int = Field(10, ge=1, le=2000, validation_alias="ITEM_DESCRIPTION_MIN_LENGTH")
    descricao_item_maxima: int = Field(2000, ge=1, le=2000, validation_alias="ITEM_DESCRIPTION_MAX_LENGTH")
    fotos_minimas: int = Field(3, ge=0, validation_alias="ITEM_MIN_PHOTOS")
    fotos_maximas: int = Field(10, ge=0, validation_alias="ITEM_MAX_PHOTOS")
    foto_maxima_bytes: int = Field(5242880, gt=0, validation_alias="PHOTO_MAX_BYTES")
    foto_tipos_permitidos: ListaConfigurada = Field(
        ("image/jpeg", "image/png", "image/webp"), validation_alias="PHOTO_ALLOWED_MIME_TYPES"
    )
    categorias: ListaConfigurada = Field(
        ("Eletrônicos", "Casa e decoração", "Moda", "Esportes e lazer", "Colecionáveis", "Livros e mídia", "Outros"),
        validation_alias="CATEGORIES",
    )

    @field_validator("database_url")
    @classmethod
    def validar_database_url(cls, valor: SecretStr) -> SecretStr:
        try:
            url = make_url(valor.get_secret_value())
            valido = url.drivername == "postgresql+psycopg" and bool(url.database)
        except (ArgumentError, ValueError, TypeError):
            # Nao repassar erros do parser: podem conter a URL.
            valido = False
        if not valido:
            raise ValueError("DATABASE_URL deve indicar PostgreSQL com driver postgresql+psycopg e banco definido")
        return valor

    @field_validator("categorias", "foto_tipos_permitidos", mode="before")
    @classmethod
    def converter_listas(cls, valor, info):
        if isinstance(valor, str):
            separador = "|" if info.field_name == "categorias" else ","
            valor = tuple(parte.strip() for parte in valor.split(separador))
        if not valor or any(not isinstance(parte, str) or not parte.strip() for parte in valor):
            raise ValueError("a lista deve conter valores nao vazios")
        partes = tuple(parte.strip() for parte in valor)
        if len(set(partes)) != len(partes):
            raise ValueError("a lista nao pode conter valores repetidos")
        return partes

    @model_validator(mode="after")
    def validar_intervalos(self):
        pares = (
            ("ITEM_NAME_MIN_LENGTH", self.nome_item_minimo, "ITEM_NAME_MAX_LENGTH", self.nome_item_maximo),
            ("ITEM_DESCRIPTION_MIN_LENGTH", self.descricao_item_minima, "ITEM_DESCRIPTION_MAX_LENGTH", self.descricao_item_maxima),
            ("ITEM_MIN_PHOTOS", self.fotos_minimas, "ITEM_MAX_PHOTOS", self.fotos_maximas),
            ("AUCTION_MIN_ADVANCE_SECONDS", self.antecedencia_minima_segundos, "AUCTION_MAX_ADVANCE_SECONDS", self.antecedencia_maxima_segundos),
            ("AUCTION_MIN_DURATION_SECONDS", self.duracao_minima_segundos, "AUCTION_MAX_DURATION_SECONDS", self.duracao_maxima_segundos),
        )
        for nome_minimo, minimo, nome_maximo, maximo in pares:
            if minimo > maximo:
                raise ValueError(f"{nome_minimo} deve ser menor ou igual a {nome_maximo}")
        return self


@lru_cache(maxsize=1)
def obter_configuracoes() -> Configuracoes:
    return Configuracoes()
