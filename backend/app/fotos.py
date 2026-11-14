"""Referencias de fotos (RF07). Placeholder ate o cartao F11.

O contrato (docs/contratos.md) define o fluxo: a tela envia cada foto a
POST /api/fotos, recebe uma referencia opaca e, ao criar o leilao, manda a lista
de referencias. O backend nunca aceita URL arbitraria como prova de upload.

Enquanto o F11 nao existir, nenhuma referencia e reconhecida: qualquer foto e
recusada com 422. Criar leilao sem fotos exige ITEM_MIN_PHOTOS=0 (so em
desenvolvimento/versao minima, como o contrato ja preve).
O F11 substitui apenas resolver(), mantendo a assinatura.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class FotoResolvida:
    url: str
    chave_armazenamento: str | None


class ReferenciaInvalida(Exception):
    def __init__(self, posicao: int):
        super().__init__(f"referencia {posicao} invalida")
        self.posicao = posicao


def resolver(db: Session, usuario_id: int, referencias: list[str]) -> list[FotoResolvida]:
    """Confere que cada referencia existe e pertence ao usuario; devolve URL e chave."""
    if referencias:
        raise ReferenciaInvalida(1)
    return []
