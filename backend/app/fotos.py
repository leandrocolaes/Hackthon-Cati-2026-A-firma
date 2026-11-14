"""Fotos dos itens (RF07), guardadas no PostgreSQL (tabela arquivos_fotos).

Fluxo do contrato (docs/contratos.md): a tela envia cada foto a POST /api/fotos,
recebe uma referencia opaca e, ao criar o leilao, manda a lista de referencias.
O backend nunca aceita URL arbitraria: so referencias que existem e sao do usuario.

O tipo e decidido pelos primeiros bytes do arquivo, nao pelo nome nem pelo
Content-Type enviado pelo navegador (ambos sao faceis de falsificar).
"""

from dataclasses import dataclass
import secrets

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.config import Configuracoes
from app.models import ArquivoFoto


@dataclass(frozen=True)
class FotoResolvida:
    url: str
    chave_armazenamento: str | None


class ReferenciaInvalida(Exception):
    def __init__(self, posicao: int):
        super().__init__(f"referencia {posicao} invalida")
        self.posicao = posicao


class FotoInvalida(Exception):
    """Motivo pronto para mostrar ao usuario."""


def url_da_foto(referencia: str) -> str:
    return f"/api/fotos/{referencia}"


def tipo_pelo_conteudo(dados: bytes) -> str | None:
    if dados.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if dados.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(dados) >= 12 and dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "image/webp"
    return None


def guardar(db: Session, cfg: Configuracoes, usuario_id: int, dados: bytes) -> str:
    """Valida e grava; devolve a referencia. `dados` pode ter 1 byte a mais que o limite
    (quem le corta em limite+1 para saber se passou sem ler o arquivo inteiro)."""
    if not dados:
        raise FotoInvalida("O arquivo está vazio.")
    if len(dados) > cfg.foto_maxima_bytes:
        raise FotoInvalida(f"A foto passa do limite de {cfg.foto_maxima_bytes // (1024 * 1024)} MB.")
    tipo = tipo_pelo_conteudo(dados)
    if tipo is None or tipo not in cfg.foto_tipos_permitidos:
        raise FotoInvalida("Formato não aceito. Envie JPEG, PNG ou WebP.")
    referencia = secrets.token_urlsafe(24)  # 32 caracteres, impossivel de adivinhar
    db.execute(insert(ArquivoFoto).values(referencia=referencia, usuario_id=usuario_id, tipo=tipo,
                                          tamanho=len(dados), dados=dados))
    db.commit()
    return referencia


def ler(db: Session, referencia: str) -> tuple[str, bytes] | None:
    if len(referencia) > 64:
        return None
    linha = db.execute(select(ArquivoFoto.tipo, ArquivoFoto.dados)
                       .where(ArquivoFoto.referencia == referencia)).first()
    return (linha.tipo, linha.dados) if linha else None


def resolver(db: Session, usuario_id: int, referencias: list[str]) -> list[FotoResolvida]:
    """Confere que cada referencia existe e pertence ao usuario; devolve URL e chave."""
    if not referencias:
        return []
    minhas = set(db.execute(select(ArquivoFoto.referencia).where(
        ArquivoFoto.referencia.in_(referencias), ArquivoFoto.usuario_id == usuario_id)).scalars())
    for posicao, referencia in enumerate(referencias, start=1):
        if referencia not in minhas:
            raise ReferenciaInvalida(posicao)
    return [FotoResolvida(url=url_da_foto(r), chave_armazenamento=r) for r in referencias]
