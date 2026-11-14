"""Processo de fundo: abre e fecha leiloes sozinho (RF17, RF18).

Roda como o servico "worker" do compose.yaml, com a mesma imagem do backend:
    python -m app.worker

Um laco simples: a cada INTERVALO_SEGUNDOS chama servicos.agenda.ciclo. Se algo
falhar (banco reiniciando, migracao ainda nao aplicada), registra o erro e tenta
de novo na proxima volta, sem morrer. Nao roda migracoes (sao manuais; ver README).
"""

import logging
import signal
import time

from app.db import SessionLocal
from app.servicos.agenda import ciclo

# DECISAO: 1 s. Um leilao fecha no maximo ~1 s depois do termino; os lances ja sao
# recusados no instante exato pelo relogio do banco, entao o atraso so afeta quando
# o resultado aparece.
INTERVALO_SEGUNDOS = 1.0

log = logging.getLogger("worker")
_parar = False


def _ao_receber_sinal(*_):
    global _parar
    _parar = True


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    signal.signal(signal.SIGTERM, _ao_receber_sinal)  # docker compose stop
    signal.signal(signal.SIGINT, _ao_receber_sinal)   # Ctrl+C
    log.info("worker iniciado (intervalo %.1fs)", INTERVALO_SEGUNDOS)
    while not _parar:
        try:
            with SessionLocal() as db:
                abertos, fechados = ciclo(db)
            for leilao_id in abertos:
                log.info("leilao %s aberto", leilao_id)
            for leilao_id, estado in fechados.items():
                log.info("leilao %s fechado: %s", leilao_id, estado)
        except Exception as erro:
            # Sem traceback: a mensagem do driver pode conter a URL do banco.
            log.error("falha no ciclo (%s); tentando de novo", type(erro).__name__)
        time.sleep(INTERVALO_SEGUNDOS)
    log.info("worker encerrado")


if __name__ == "__main__":
    main()
