"""Regras de negocio puras (sem banco). Mudar uma regra = mudar uma funcao aqui.

Cada funcao recebe o estado e devolve a decisao, sempre igual para o mesmo estado
(exigencia do RF14). Testadas em tests/test_regras.py.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from app.config import Configuracoes


# RF14 (fase 2): incremento pela faixa do preco atual confirmado. Cada linha vale
# para precos MENORES que o limite; acima do ultimo limite vale o ultimo incremento.
FAIXAS_INCREMENTO: tuple[tuple[Decimal, Decimal], ...] = (
    (Decimal("100.00"), Decimal("1.00")),
    (Decimal("500.00"), Decimal("5.00")),
    (Decimal("1000.00"), Decimal("10.00")),
    (Decimal("5000.00"), Decimal("50.00")),
    (Decimal("25000.00"), Decimal("100.00")),
)
INCREMENTO_MAXIMO = Decimal("500.00")


def incremento(preco_atual: Decimal) -> Decimal:
    """Incremento da faixa de preco_atual (tabela da secao 2.2 da fase 2)."""
    for limite, valor in FAIXAS_INCREMENTO:
        if preco_atual < limite:
            return valor
    return INCREMENTO_MAXIMO


def lance_minimo(preco_inicial: Decimal, preco_atual: Decimal, tem_lider: bool) -> Decimal:
    """RF14. Sem lances, o minimo e o preco inicial (o primeiro lance pode ser igual a ele).
    Com lances, e o preco atual + incremento da faixa desse preco atual. "Ha lance" e
    decidido pelo lider, nunca comparando precos (docs/dominio.md, item 6).

    A faixa sai sempre do estado confirmado no servidor (preco_atual lido sob a trava),
    nunca do valor que o navegador mostrava.
    """
    if not tem_lider:
        return preco_inicial
    return preco_atual + incremento(preco_atual)


def hard_end(termino_original: datetime, cfg: Configuracoes) -> datetime:
    """RF15: teto absoluto do termino (termino original + AUCTION_EXTENSION_MAX_SECONDS,
    padrao 10 min). Nenhuma prorrogacao passa daqui."""
    return termino_original + timedelta(seconds=cfg.prorrogacao_maxima_segundos)


def prorrogacao_esgotada(termino_vigente: datetime, termino_original: datetime, cfg: Configuracoes) -> bool:
    """True quando o termino vigente ja chegou ao hard end: o encerramento e definitivo."""
    return termino_vigente >= hard_end(termino_original, cfg)


def novo_termino(instante: datetime, termino_vigente: datetime, termino_original: datetime,
                 cfg: Configuracoes) -> datetime | None:
    """RF15. Devolve o novo termino se o lance aceito prorroga o leilao; senao None.

    DECISAO da equipe: lance aceito com menos de AUCTION_EXTENSION_WINDOW_SECONDS
    restantes leva o termino para instante + AUCTION_EXTENSION_SECONDS, sem passar de
    termino_original + AUCTION_EXTENSION_MAX_SECONDS. O termino nunca diminui.
    """
    if termino_vigente - instante >= timedelta(seconds=cfg.prorrogacao_janela_segundos):
        return None
    teto = hard_end(termino_original, cfg)
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


def edicao_permitida(estado: str, instante: datetime, inicio: datetime, tem_lances: bool) -> bool:
    """RF23: so leilao Agendado, antes do inicio e ainda sem lances.

    Depois que o leilao inicia ou recebe lance, nome, descricao, categoria,
    preco inicial, inicio e duracao ficam bloqueados.
    """
    return estado == "agendado" and instante < inicio and not tem_lances
