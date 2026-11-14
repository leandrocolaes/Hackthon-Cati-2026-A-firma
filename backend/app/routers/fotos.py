"""Envio e exibicao de fotos (RF07, docs/contratos.md).

    POST /api/fotos               -> 201 {referencia, url}   (sessao valida; multipart "arquivo")
    GET  /api/fotos/{referencia}  -> bytes da imagem          (publico: catalogo e detalhe sao publicos)
"""

from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy.orm import Session

from app import fotos
from app.config import Configuracoes, obter_configuracoes
from app.db import get_db
from app.erros import ErroApi
from app.servicos.leiloes import invalido
from app.sessoes import UsuarioLogado, usuario_atual

router = APIRouter(prefix="/api", tags=["fotos"])


@router.post("/fotos", status_code=201)
def enviar(arquivo: UploadFile = File(...), usuario: UsuarioLogado = Depends(usuario_atual),
           cfg: Configuracoes = Depends(obter_configuracoes), db: Session = Depends(get_db)):
    dados = arquivo.file.read(cfg.foto_maxima_bytes + 1)  # nunca le mais que o limite + 1
    try:
        referencia = fotos.guardar(db, cfg, usuario.id, dados)
    except fotos.FotoInvalida as e:
        raise invalido("arquivo", str(e))
    return {"referencia": referencia, "url": fotos.url_da_foto(referencia)}


@router.get("/fotos/{referencia}")
def mostrar(referencia: str, db: Session = Depends(get_db)):
    achada = fotos.ler(db, referencia)
    if achada is None:
        raise ErroApi(404, "recurso_nao_encontrado", "Foto não encontrada.")
    tipo, dados = achada
    # Conteudo de uma referencia nunca muda: o navegador pode guardar para sempre.
    return Response(content=dados, media_type=tipo, headers={
        "Cache-Control": "public, max-age=31536000, immutable",
        "X-Content-Type-Options": "nosniff",
    })
