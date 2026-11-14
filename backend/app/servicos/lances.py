"""Lance (RF10, RF11, RF12, RF14, RF15, RF16). Fluxo aprovado em docs/dominio.md, item 10.

  Fora da transacao (nao viram tentativa gravada): sessao 401, formato 422, leilao 404.
  BEGIN
    1. SELECT leilao ... FOR UPDATE      <- lances NESTE leilao fazem fila aqui
    2. tentativa (usuario, chave)?       <- sob a trava: o reenvio enxerga o resultado do 1o
         existe -> ROLLBACK; resposta original (ou 409 chave_reutilizada)
    3. instante = clock_timestamp()      <- depois da trava (RF16)
    4. sessao ainda vale? senao 401, sem gravar
    5. participante? senao 409 participante_ausente (gravada)
    5b. RF13: ultima tentativa DECIDIDA deste usuario neste leilao ha menos de
        BID_MIN_INTERVAL_SECONDS? -> 429 lance_muito_rapido, SEM gravar tentativa
        (assim o reenvio da mesma chave depois do intervalo e decidido normalmente)
    5c. decide (estado/prazo, comitente, lider, valor >= minimo)
    6. aceito -> INSERT lance; UPDATE leilao (preco, lider, termino, contador, versao+1)
    7. INSERT tentativa COMPLETA (situacao, status_http, resposta_original, lance_id)
  COMMIT
    violou uq_tentativas_lance_usuario_chave (mesma chave, mesmo instante, leiloes
    diferentes) -> ROLLBACK de tudo; nova transacao le a original e devolve.

"Ordem de chegada" = ordem em que o servidor obtem a trava (dominio, item 14).
"""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import exists, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import dinheiro
from app.config import Configuracoes
from app.erros import ErroApi, corpo_erro
from app.models import Lance, Leilao, Participante, Sessao, TentativaLance
from app.regras import espera_para_lance, impedimento, lance_minimo, novo_termino
from app.servicos.leiloes import nao_encontrado
from app.tempo import agora

RESTRICAO_CHAVE = "uq_tentativas_lance_usuario_chave"

# DECISAO: textos das recusas. Os codigos sao os de docs/contratos.md (o frontend usa
# os codigos); os textos podem ser ajustados livremente.
MENSAGENS = {
    "participante_ausente": "Entre na sala do leilão para dar lances.",
    "leilao_fora_do_estado": "O leilão ainda não começou.",
    "leilao_encerrado": "O leilão já terminou.",
    "lance_do_comitente": "O comitente não pode dar lance no próprio leilão.",
    "lance_do_lider": "Você já é o líder; espere outro lance para cobrir.",
    "lance_abaixo_do_minimo": "O valor está abaixo do mínimo atual.",
    "chave_reutilizada": "Esta tentativa já foi usada com outro valor ou leilão.",
}
# RF13: recusa de frequencia. 429 = "cedo demais"; nao e recusa de regra do leilao.
STATUS_MUITO_RAPIDO = 429


@dataclass
class Resposta:
    status: int
    corpo: dict


def dar_lance(db: Session, cfg: Configuracoes, leilao_id: int, usuario_id: int,
              sessao_id: int, chave: UUID, valor: Decimal) -> Resposta:
    if not db.execute(select(exists().where(Leilao.id == leilao_id))).scalar():
        db.rollback()
        raise nao_encontrado()
    db.rollback()  # a transacao do lance comeca do zero
    try:
        return _processar(db, cfg, leilao_id, usuario_id, sessao_id, chave, valor)
    except IntegrityError as erro:
        db.rollback()
        restricao = getattr(getattr(erro.orig, "diag", None), "constraint_name", None)
        if restricao != RESTRICAO_CHAVE:
            raise  # outra violacao seria bug: nao esconder
        original = db.execute(select(TentativaLance).where(
            TentativaLance.usuario_id == usuario_id, TentativaLance.chave == chave)).scalar_one()
        resposta = _reenvio(original, leilao_id, valor)
        db.rollback()
        return resposta


def _reenvio(original: TentativaLance, leilao_id: int, valor: Decimal) -> Resposta:
    """RF12: a mesma tentativa devolve exatamente o resultado gravado, sem marca de replay."""
    if original.leilao_id != leilao_id or original.valor_solicitado != valor:
        return Resposta(409, corpo_erro("chave_reutilizada", MENSAGENS["chave_reutilizada"]))
    return Resposta(original.status_http, original.resposta_original)


def _processar(db: Session, cfg: Configuracoes, leilao_id: int, usuario_id: int,
               sessao_id: int, chave: UUID, valor: Decimal) -> Resposta:
    leilao = db.execute(select(Leilao).where(Leilao.id == leilao_id).with_for_update()).scalar_one()

    original = db.execute(select(TentativaLance).where(
        TentativaLance.usuario_id == usuario_id, TentativaLance.chave == chave)).scalar_one_or_none()
    if original is not None:
        resposta = _reenvio(original, leilao_id, valor)
        db.rollback()
        return resposta

    instante = agora(db)
    if not db.execute(select(exists().where(Sessao.id == sessao_id, Sessao.expira_em > instante))).scalar():
        db.rollback()
        raise ErroApi(401, "sessao_invalida", "Sessão inválida ou expirada. Entre novamente.")

    minimo = lance_minimo(leilao.preco_inicial, leilao.preco_atual, leilao.lider_id is not None)
    participante = db.execute(select(exists().where(
        Participante.leilao_id == leilao_id, Participante.usuario_id == usuario_id))).scalar()
    if not participante:
        codigo = "participante_ausente"
    else:
        ultima = db.execute(select(func.max(TentativaLance.criado_em)).where(
            TentativaLance.usuario_id == usuario_id, TentativaLance.leilao_id == leilao_id)).scalar_one()
        espera = espera_para_lance(ultima, instante, cfg)
        if espera is not None:
            db.rollback()  # nao grava: nao e uma decisao sobre o lance, so "tente depois"
            return Resposta(STATUS_MUITO_RAPIDO, corpo_erro(
                "lance_muito_rapido", f"Aguarde {espera} s para dar outro lance neste leilão.",
                {"segundos_restantes": espera}))
        codigo = impedimento(leilao.estado, instante, leilao.termino_vigente,
                             usuario_id, leilao.comitente_id, leilao.lider_id)
        if codigo is None and valor < minimo:
            codigo = "lance_abaixo_do_minimo"

    if codigo:
        detalhes = {} if codigo == "participante_ausente" else {"lance_minimo": dinheiro.texto(minimo)}
        corpo = corpo_erro(codigo, MENSAGENS[codigo], detalhes)
        _gravar_tentativa(db, usuario_id, leilao_id, chave, valor, None, 409, corpo, instante)
        db.commit()
        return Resposta(409, corpo)

    lance_id = db.execute(insert(Lance).values(
        leilao_id=leilao_id, usuario_id=usuario_id, valor=valor,
        criado_em=instante,  # explicito: o DEFAULT now() seria o inicio da transacao (dominio, item 12)
    ).returning(Lance.id)).scalar_one()
    mudancas = {"preco_atual": valor, "lider_id": usuario_id, "versao": Leilao.versao + 1}
    fim = novo_termino(instante, leilao.termino_vigente, leilao.termino_original, cfg)
    if fim is not None:  # RF15: prorrogacao na mesma operacao (versao sobe uma vez so)
        mudancas.update(termino_vigente=fim, prorrogacoes=Leilao.prorrogacoes + 1)
    nova_versao = db.execute(update(Leilao).where(Leilao.id == leilao_id).values(**mudancas)
                             .returning(Leilao.versao)).scalar_one()

    corpo = {"lance_id": lance_id, "leilao_id": leilao_id, "valor": dinheiro.texto(valor), "versao": nova_versao}
    _gravar_tentativa(db, usuario_id, leilao_id, chave, valor, lance_id, 201, corpo, instante)
    db.commit()
    return Resposta(201, corpo)


def _gravar_tentativa(db, usuario_id, leilao_id, chave, valor, lance_id, status, corpo, instante):
    db.execute(insert(TentativaLance).values(
        usuario_id=usuario_id, leilao_id=leilao_id, chave=chave, valor_solicitado=valor,
        criado_em=instante,  # relogio da decisao (RF13 mede o intervalo por aqui), nao o inicio da transacao
        lance_id=lance_id, situacao="aceita" if lance_id else "recusada",
        status_http=status, resposta_original=corpo,
    ))
