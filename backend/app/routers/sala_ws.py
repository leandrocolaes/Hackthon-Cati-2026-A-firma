"""WS /api/leiloes/{id}/ws: atualizacoes da sala (docs/contratos.md).

Recebe atualizacoes do servidor; NAO e o canal de envio de lances (lance e POST).
Fechamentos: 4401 sessao invalida/expirada; 4403 sem participacao; 4404 leilao inexistente;
4409 espectador em leilao que nao esta em andamento.

?modo=espectador (RF25): sem cookie e sem participacao; snapshot publico.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from app import tempo_real
from app.config import obter_configuracoes

router = APIRouter()


@router.websocket("/api/leiloes/{leilao_id}/ws")
async def sala_ao_vivo(ws: WebSocket, leilao_id: int, modo: str = "participante"):
    if modo == "espectador":
        codigo = await run_in_threadpool(tempo_real.autorizar_espectador, leilao_id)
        usuario_id = token_hash = None
    else:
        # O cookie de sessao chega no handshake (mesma origem via Nginx).
        token = ws.cookies.get(obter_configuracoes().sessao_cookie_nome)
        codigo, usuario_id, token_hash = await run_in_threadpool(tempo_real.autorizar, token, leilao_id)
    await ws.accept()  # 101; recusas sao comunicadas pelo codigo de fechamento
    if codigo:
        await ws.close(code=codigo)
        return
    conexao = tempo_real.Conexao(ws=ws, leilao_id=leilao_id, usuario_id=usuario_id, token_hash=token_hash)
    tempo_real.salas.entrar(conexao)
    try:
        await tempo_real.enviar(conexao)  # snapshot inicial: quem chega ou reconecta fica em dia
        while True:
            await ws.receive_text()  # o cliente nao precisa mandar nada; so mantemos aberta
    except WebSocketDisconnect:
        pass
    finally:
        tempo_real.salas.sair(conexao)
