"""Formato unico de erro da API (docs/contratos.md, "Erros e reenvio").

    {"codigo": "lance_abaixo_do_minimo", "mensagem": "...", "detalhes": {...}}

- Rotas e servicos levantam ErroApi(status, codigo, mensagem, detalhes).
- Erros de validacao do FastAPI/Pydantic viram 422 "entrada_invalida", listando so
  campo e motivo; nunca o valor recebido (que pode ser senha ou token).
- Rota inexistente vira 404 "recurso_nao_encontrado".
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErroApi(Exception):
    def __init__(self, status: int, codigo: str, mensagem: str, detalhes: dict[str, Any] | None = None):
        super().__init__(mensagem)
        self.status = status
        self.codigo = codigo
        self.mensagem = mensagem
        self.detalhes = detalhes or {}


def corpo_erro(codigo: str, mensagem: str, detalhes: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"codigo": codigo, "mensagem": mensagem, "detalhes": detalhes or {}}


def _campo(loc: tuple) -> str:
    # ("body", "email") -> "email"; ("query", "pagina") -> "pagina"; ("body",) -> "corpo"
    partes = [str(p) for p in loc if p not in ("body", "query", "path", "header", "cookie")]
    return ".".join(partes) or "corpo"


def _motivo(erro: dict) -> str:
    msg = str(erro.get("msg", "valor invalido"))
    return msg.removeprefix("Value error, ")


def registrar(app: FastAPI) -> None:
    @app.exception_handler(ErroApi)
    async def _erro_api(request: Request, erro: ErroApi):
        return JSONResponse(status_code=erro.status, content=corpo_erro(erro.codigo, erro.mensagem, erro.detalhes))

    @app.exception_handler(RequestValidationError)
    async def _validacao(request: Request, erro: RequestValidationError):
        campos = [{"campo": _campo(e.get("loc", ())), "motivo": _motivo(e)} for e in erro.errors()]
        return JSONResponse(status_code=422, content=corpo_erro(
            "entrada_invalida", "Confira os campos informados.", {"campos": campos}))

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, erro: StarletteHTTPException):
        if erro.status_code == 404:
            return JSONResponse(status_code=404, content=corpo_erro("recurso_nao_encontrado", "Recurso não encontrado."))
        return JSONResponse(status_code=erro.status_code, content=corpo_erro("erro_http", str(erro.detail)),
                            headers=getattr(erro, "headers", None))
