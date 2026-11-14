"""Importe este pacote para registrar os modelos em Base.metadata."""

from app.models.usuario import Usuario
from app.models.sessao import Sessao

__all__ = ["Usuario", "Sessao"]
