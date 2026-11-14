"""Lance e sala (docs/contratos.md).

    POST /api/leiloes/{id}/lances  {"valor": "10.00", "chave": "<uuid>"}
         201 {lance_id, leilao_id, valor, versao} | 409 recusa {codigo, mensagem, detalhes}
    GET  /api/leiloes/{id}/sala    snapshot personalizado (exige participacao)
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app import dinheiro
from app.config import Configuracoes, obter_configuracoes
from app.db import get_db
from app.servicos import lances, sala
from app.sessoes import UsuarioLogado, usuario_atual, usuario_atual_sem_renovar

router = APIRouter(prefix="/api/leiloes", tags=["lances e sala"])


class LanceEntrada(BaseModel):
    # Texto, para nao passar por float no JSON (RF19).
    valor: str = Field(max_length=30)
    # Gerada pelo navegador NO CLIQUE e reenviada igual numa nova tentativa (RF12).
    chave: UUID

    @field_validator("valor")
    @classmethod
    def _valor(cls, v: str) -> str:
        return dinheiro.texto(dinheiro.ler(v))  # ValueError -> 422 entrada_invalida


@router.post("/{leilao_id}/lances")
def dar_lance(leilao_id: int, dados: LanceEntrada, usuario: UsuarioLogado = Depends(usuario_atual),
              cfg: Configuracoes = Depends(obter_configuracoes), db: Session = Depends(get_db)):
    r = lances.dar_lance(db, cfg, leilao_id, usuario.id, usuario.sessao_id,
                         dados.chave, dinheiro.ler(dados.valor))
    return JSONResponse(status_code=r.status, content=r.corpo)


@router.get("/{leilao_id}/sala")
def ver_sala(leilao_id: int, usuario: UsuarioLogado = Depends(usuario_atual_sem_renovar),
             cfg: Configuracoes = Depends(obter_configuracoes), db: Session = Depends(get_db)):
    """Consultada em polling pela tela: NAO renova a sessao (expira por inatividade humana)."""
    return sala.snapshot(db, cfg, leilao_id, usuario.id)
