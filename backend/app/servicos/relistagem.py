"""Relistagem (RF28): novo leilao a partir de um finalizado ou cancelado.

POST /api/leiloes/{id}/relistar com o MESMO corpo da criacao. A tela pre-preenche o
formulario com o detalhe publico do leilao de origem (nome, descricao, categoria,
preco inicial e fotos); inicio e duracao ficam em branco e sao exigidos de novo.

DECISAO: cria um ITEM NOVO (copia editavel), em vez de reaproveitar o item antigo,
para que mudar nome/descricao nao altere o anuncio historico do leilao encerrado
(docs/dominio.md, item 3). As fotos sao referencias do proprio comitente, que o F11
ja permite usar em mais de um leilao.

O leilao novo nasce como um leilao criado do zero: novo id, agendado, sem lances,
lider, participantes, vencedor, resultado, prorrogacoes nem prazos herdados.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Configuracoes
from app.erros import ErroApi
from app.models import Leilao
from app.regras import relistagem_permitida
from app.schemas.leiloes import LeilaoCriado, LeilaoCriar
from app.servicos.leiloes import criar, nao_encontrado


def relistar(db: Session, cfg: Configuracoes, origem_id: int, usuario_id: int, dados: LeilaoCriar) -> LeilaoCriado:
    # Trava a origem: nao ha transicao possivel a partir de estado final, mas assim a
    # decisao usa o estado confirmado, como as demais acoes do comitente.
    origem = db.execute(select(Leilao).where(Leilao.id == origem_id).with_for_update()).scalar_one_or_none()
    if origem is None:
        db.rollback()
        raise nao_encontrado()
    if origem.comitente_id != usuario_id:
        db.rollback()
        raise ErroApi(403, "relistagem_nao_autorizada", "Só o comitente pode relistar este item.")
    if not relistagem_permitida(origem.estado):
        db.rollback()
        raise ErroApi(409, "relistagem_nao_permitida",
                      "Só dá para relistar leilão vendido, encerrado sem lances ou cancelado.")
    try:
        return criar(db, cfg, usuario_id, dados)  # mesmas validacoes da criacao; faz o commit
    except ErroApi:
        db.rollback()
        raise
