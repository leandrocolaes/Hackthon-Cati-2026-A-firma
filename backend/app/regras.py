"""Regras de negocio puras (sem banco). Mudar uma regra = mudar uma funcao aqui.

Cada funcao recebe o estado e devolve a decisao, sempre igual para o mesmo estado
(exigencia do RF14). Testadas em tests/test_regras.py.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from app.config import Configuracoes


def lance_minimo(preco_inicial: Decimal, preco_atual: Decimal, tem_lider: bool, cfg: Configuracoes) -> Decimal:
    """RF14. DECISAO da equipe: incremento fixo (BID_INCREMENT_CENTS, padrao R$ 1,00).

    Sem lances, o minimo e o preco inicial (o primeiro lance pode ser igual a ele).
    Com lances, e o preco atual + incremento. "Ha lance" e decidido pelo lider,
    nunca comparando precos (docs/dominio.md, item 6).

    Evolucao planejada: incremento por faixa de preco e crescente com o numero de
    prorrogacoes; basta trocar o corpo desta funcao (leiloes.prorrogacoes ja existe).
    """
    if not tem_lider:
        return preco_inicial
    return preco_atual + Decimal(cfg.incremento_centavos) / 100


def novo_termino(instante: datetime, termino_vigente: datetime, termino_original: datetime,
                 cfg: Configuracoes) -> datetime | None:
    """RF15. Devolve o novo termino se o lance aceito prorroga o leilao; senao None.

    DECISAO da equipe: lance aceito com menos de AUCTION_EXTENSION_WINDOW_SECONDS
    restantes leva o termino para instante + AUCTION_EXTENSION_SECONDS, sem passar de
    termino_original + AUCTION_EXTENSION_MAX_SECONDS. O termino nunca diminui.
    """
    if termino_vigente - instante >= timedelta(seconds=cfg.prorrogacao_janela_segundos):
        return None
    teto = termino_original + timedelta(seconds=cfg.prorrogacao_maxima_segundos)
    candidato = min(instante + timedelta(seconds=cfg.prorrogacao_segundos), teto)
    return candidato if candidato > termino_vigente else None


def impedimento(estado: str, instante: datetime, termino_vigente: datetime,
                usuario_id: int, comitente_id: int, lider_id: int | None) -> str | None:
    """Por que este participante nao pode dar lance agora (alem do valor), ou None.

    Codigos de docs/contratos.md. Usado pelo lance (decisao oficial, sob a trava) e
    pela sala (pode_dar_lance / motivo_impedimento, so informativo).
    """
    if estado == "agendado":
        return "leilao_fora_do_estado"
    if estado != "em_andamento" or instante >= termino_vigente:
        return "leilao_encerrado"
    if usuario_id == comitente_id:
        return "lance_do_comitente"
    if usuario_id == lider_id:
        return "lance_do_lider"
    return None


def cancelamento_permitido(estado: str, instante: datetime, termino_vigente: datetime, tem_lider: bool) -> bool:
    """RF08. Agendado; ou em andamento SEM lances e antes do termino.

    DECISAO: em andamento so ate o termino. Um leilao vencido sem lances deve virar
    "encerrado sem lances" (worker), e nao "cancelado", nao importa quem chegue antes.
    """
    return estado == "agendado" or (estado == "em_andamento" and not tem_lider and instante < termino_vigente)


def edicao_permitida(estado: str, instante: datetime, inicio: datetime, outros_participantes: int,
                     cfg: Configuracoes) -> bool:
    """DECISAO da equipe: so leilao agendado (antes do inicio) e, alem disso, se ninguem
    alem do comitente entrou na sala OU se falta mais que AUCTION_EDIT_MIN_ADVANCE_SECONDS
    (padrao 10 min) para o inicio. Quem esta na sala recebe o estado novo na hora."""
    if estado != "agendado" or instante >= inicio:
        return False
    return outros_participantes == 0 or (inicio - instante).total_seconds() > cfg.edicao_antecedencia_segundos
