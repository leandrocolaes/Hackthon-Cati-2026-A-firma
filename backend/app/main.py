"""Ponto de entrada da API. Tem só duas rotas, para provar as conexões:

- GET /api/health  → frontend ↔ backend ↔ banco (HTTP)
- WS  /api/ws      → frontend ↔ backend em tempo real (WebSocket)

Todas as rotas começam com /api porque é assim que o Nginx sabe
o que mandar para cá (o resto é o site React).
"""
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db

app = FastAPI(docs_url="/api/docs", openapi_url="/api/openapi.json")


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    try:
        # Pergunta a hora ao banco: se responder, a conexão funciona.
        db_time = db.execute(text("SELECT now()")).scalar_one()
        return {"api": "ok", "db": "ok", "db_time": db_time}
    except Exception as e:
        return {"api": "ok", "db": f"erro: {e.__class__.__name__}"}


@app.websocket("/api/ws")
async def ws_echo(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            msg = await ws.receive_text()
            # Devolve a mensagem com o horário do servidor (que é o que vale — RF16).
            now = datetime.now(timezone.utc).isoformat()
            await ws.send_json({"echo": msg, "server_time": now})
    except WebSocketDisconnect:
        pass
