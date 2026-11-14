"""Sala em tempo real (RF09; docs/contratos.md, "Versao e comunicacao worker/API").

Sem LISTEN/NOTIFY nesta versao (decisao do contrato). Como funciona:
  1. Cada navegador na sala abre WS /api/leiloes/{id}/ws (cookie de sessao no handshake).
  2. Ao conectar, recebe o snapshot completo da sala (reconecta ja em dia).
  3. Uma tarefa de fundo consulta, a cada INTERVALO_SEGUNDOS, a versao dos leiloes que
     tem conexoes abertas. Se a versao subiu (lance, abertura, fechamento,
     cancelamento - API ou worker), rele o snapshot JA CONFIRMADO e envia.
  4. O snapshot e personalizado (meu_participante_id, pode_dar_lance): cada conexao
     recebe o seu, nunca um compartilhado.

Atraso tipico: ate ~1 s, alem de rede/processamento. Pode agrupar mudancas
intermediarias: e um "estado atual", nao um log de eventos.
Expiracao: a sessao e reconferida a cada envio e a cada VERIFICAR_SESSAO_SEGUNDOS;
sessao vencida fecha a conexao com 4401. Assistir nao renova a sessao.
"""

import asyncio
from dataclasses import dataclass, field
import logging
import time

from fastapi import WebSocket
from sqlalchemy import exists, select
from starlette.concurrency import run_in_threadpool

from app import db as modulo_db
from app.config import obter_configuracoes
from app.erros import ErroApi
from app.models import Leilao, Participante, Sessao
from app.seguranca import hash_token
from app.servicos.sala import snapshot
from app.tempo import agora

log = logging.getLogger("tempo_real")

# DECISAO: 1 s (contrato). Sessoes reconferidas tambem sem mudancas a cada 30 s.
INTERVALO_SEGUNDOS = 1.0
VERIFICAR_SESSAO_SEGUNDOS = 30.0

# Codigos de fechamento (faixa 4000-4999 e livre para a aplicacao).
FECHAR_SEM_SESSAO = 4401
FECHAR_SEM_PARTICIPACAO = 4403
FECHAR_NAO_ENCONTRADO = 4404

# Ponto de troca para os testes (sessoes ligadas ao schema de teste).
fabrica_sessao = None


def _sessao():
    return (fabrica_sessao or modulo_db.SessionLocal)()


@dataclass(eq=False)
class Conexao:
    ws: WebSocket
    leilao_id: int
    usuario_id: int
    token_hash: str
    versao_enviada: int = -1
    envio: asyncio.Lock = field(default_factory=asyncio.Lock)


class Salas:
    def __init__(self):
        self.conexoes: dict[int, set[Conexao]] = {}

    def entrar(self, c: Conexao) -> None:
        self.conexoes.setdefault(c.leilao_id, set()).add(c)

    def sair(self, c: Conexao) -> None:
        grupo = self.conexoes.get(c.leilao_id)
        if grupo is not None:
            grupo.discard(c)
            if not grupo:
                self.conexoes.pop(c.leilao_id, None)

    def todas(self) -> list[Conexao]:
        return [c for grupo in self.conexoes.values() for c in grupo]


salas = Salas()


# ---------- consultas ao banco (sincronas: rodam em thread) ----------

def autorizar(token: str | None, leilao_id: int) -> tuple[int | None, int | None, str | None]:
    """(codigo_de_fechamento, usuario_id, token_hash). Valida sem renovar a sessao."""
    if not token:
        return FECHAR_SEM_SESSAO, None, None
    th = hash_token(token)
    with _sessao() as db:
        usuario_id = db.execute(select(Sessao.usuario_id).where(
            Sessao.token_hash == th, Sessao.expira_em > agora(db))).scalar_one_or_none()
        if usuario_id is None:
            return FECHAR_SEM_SESSAO, None, None
        if not db.execute(select(exists().where(Leilao.id == leilao_id))).scalar():
            return FECHAR_NAO_ENCONTRADO, None, None
        if not db.execute(select(exists().where(Participante.leilao_id == leilao_id,
                                                Participante.usuario_id == usuario_id))).scalar():
            return FECHAR_SEM_PARTICIPACAO, None, None
    return None, usuario_id, th


def sessao_valida(token_hash: str) -> bool:
    with _sessao() as db:
        return db.execute(select(exists().where(
            Sessao.token_hash == token_hash, Sessao.expira_em > agora(db)))).scalar()


def montar(c: Conexao) -> tuple[int | None, dict | None]:
    """(codigo_de_fechamento, snapshot). Reconfere a sessao antes de montar."""
    if not sessao_valida(c.token_hash):
        return FECHAR_SEM_SESSAO, None
    with _sessao() as db:
        try:
            return None, snapshot(db, obter_configuracoes(), c.leilao_id, c.usuario_id)
        except ErroApi as e:
            return (FECHAR_NAO_ENCONTRADO if e.status == 404 else FECHAR_SEM_PARTICIPACAO), None


def versoes(ids: list[int]) -> dict[int, int]:
    with _sessao() as db:
        return dict(db.execute(select(Leilao.id, Leilao.versao).where(Leilao.id.in_(ids))).all())


# ---------- envio ----------

async def enviar(c: Conexao) -> None:
    """Envia o snapshot atual a UMA conexao (nunca uma versao mais antiga que a ja enviada)."""
    async with c.envio:
        codigo, estado = await run_in_threadpool(montar, c)
        if codigo:
            await fechar(c, codigo)
            return
        if estado["versao"] < c.versao_enviada:
            return
        try:
            await c.ws.send_json({"tipo": "estado_leilao", "estado": estado})
            c.versao_enviada = estado["versao"]
        except Exception:
            salas.sair(c)  # navegador ja foi embora


async def fechar(c: Conexao, codigo: int) -> None:
    salas.sair(c)
    try:
        await c.ws.close(code=codigo)
    except Exception:
        pass


async def acompanhar(parar: asyncio.Event) -> None:
    """Tarefa de fundo: a cada 1 s, envia o snapshot a quem esta com versao antiga."""
    ultima_verificacao = time.monotonic()
    while not parar.is_set():
        try:
            conexoes = salas.todas()
            if conexoes:
                atuais = await run_in_threadpool(versoes, list({c.leilao_id for c in conexoes}))
                verificar_todas = time.monotonic() - ultima_verificacao >= VERIFICAR_SESSAO_SEGUNDOS
                if verificar_todas:
                    ultima_verificacao = time.monotonic()
                alvos = [c for c in conexoes
                         if verificar_todas or atuais.get(c.leilao_id, -1) > c.versao_enviada
                         or c.leilao_id not in atuais]
                await asyncio.gather(*(enviar(c) for c in alvos))
        except Exception as erro:
            # Sem traceback: mensagens do driver podem conter a URL do banco.
            log.error("falha ao atualizar salas (%s)", type(erro).__name__)
        try:
            await asyncio.wait_for(parar.wait(), timeout=INTERVALO_SEGUNDOS)
        except asyncio.TimeoutError:
            pass
