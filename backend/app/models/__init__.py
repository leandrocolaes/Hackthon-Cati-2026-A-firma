"""Importe este pacote para registrar todos os modelos em Base.metadata."""

from app.models.usuario import Usuario
from app.models.sessao import Sessao
from app.models.item import Item
from app.models.foto_item import FotoItem
from app.models.arquivo_foto import ArquivoFoto
from app.models.leilao import Leilao
from app.models.lance import Lance
from app.models.tentativa_lance import TentativaLance
from app.models.participante import Participante

__all__ = [
    "Usuario", "Sessao", "Item", "FotoItem", "ArquivoFoto", "Leilao", "Lance",
    "TentativaLance", "Participante",
]
