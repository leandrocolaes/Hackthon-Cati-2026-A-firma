"""Dados de demonstracao (RNF04): 1 comitente, 3 compradores e leiloes em todos os estados.

Uso (na raiz do repositorio, com o sistema no ar e as migracoes aplicadas):
    docker compose exec backend python -m app.seed

- Contas: criadas so se ainda nao existirem (rodar de novo nao duplica contas).
  Senha de todas: variavel DEMO_PASSWORD (padrao demo1234), lida do ambiente.
- Leiloes: cada execucao cria um lote NOVO, com horarios relativos a agora (um abre
  em 2 minutos). DECISAO: rodem de novo pouco antes da demo.

DECISAO: as fotos dos leiloes de demonstracao sao URLs publicas de exemplo, gravadas
direto como referencia, sem passar pelo armazenamento. Para mostrar o RF07 na demo,
criem um leilao pela tela com fotos reais.
"""

from datetime import timedelta
from decimal import Decimal
import os

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from app.models import FotoItem, Item, Lance, Leilao, Participante, Usuario
from app.seguranca import gerar_hash_senha, validar_senha
from app.tempo import agora

CONTAS = [
    ("Ana Comitente", "comitente@demo.local"),
    ("Bruno Comprador", "comprador1@demo.local"),
    ("Carla Compradora", "comprador2@demo.local"),
    ("Davi Comprador", "comprador3@demo.local"),
]
FOTOS_POR_ITEM = 3


def _senha_demo() -> str:
    senha = os.environ.get("DEMO_PASSWORD", "demo1234")
    motivo = validar_senha(senha)
    if motivo:
        raise SystemExit(f"DEMO_PASSWORD invalida: {motivo}")
    return senha


def _usuario(db: Session, nome: str, email: str, senha_hash: str) -> int:
    existente = db.execute(select(Usuario.id).where(Usuario.email == email)).scalar_one_or_none()
    if existente:
        return existente
    return db.execute(insert(Usuario).values(nome=nome, email=email, senha_hash=senha_hash)
                      .returning(Usuario.id)).scalar_one()


def _leilao(db, comitente, nome, categoria, preco, inicio, duracao_min, estado="agendado") -> int:
    item = db.execute(insert(Item).values(
        usuario_id=comitente, nome=nome, categoria=categoria,
        descricao=f"{nome}. Item de demonstração em ótimo estado.",
    ).returning(Item.id)).scalar_one()
    for ordem in range(FOTOS_POR_ITEM):
        texto = nome.split()[0]
        db.execute(insert(FotoItem).values(
            item_id=item, ordem=ordem, url=f"https://placehold.co/800x600/png?text={texto}+{ordem + 1}"))
    fim = inicio + timedelta(minutes=duracao_min)
    return db.execute(insert(Leilao).values(
        item_id=item, comitente_id=comitente, preco_inicial=Decimal(preco), preco_atual=Decimal(preco),
        inicio=inicio, termino_original=fim, termino_vigente=fim, estado=estado,
    ).returning(Leilao.id)).scalar_one()


def _lances(db, leilao_id, compradores, valores, instante) -> int:
    """Participantes e lances alternados (nunca o mesmo autor duas vezes seguidas)."""
    for numero, usuario in enumerate(compradores, start=1):
        db.execute(insert(Participante).values(leilao_id=leilao_id, usuario_id=usuario, numero=numero))
    ultimo = None
    for i, valor in enumerate(valores):
        autor = compradores[i % len(compradores)]
        ultimo = db.execute(insert(Lance).values(
            leilao_id=leilao_id, usuario_id=autor, valor=Decimal(valor),
            criado_em=instante - timedelta(minutes=len(valores) - i),
        ).returning(Lance.id)).scalar_one()
        db.execute(update(Leilao).where(Leilao.id == leilao_id).values(
            preco_atual=Decimal(valor), lider_id=autor, versao=Leilao.versao + 1))
    return ultimo


def popular(db: Session) -> dict[str, int]:
    """Cria contas (se faltarem) e um lote de leiloes. Devolve {estado: id}."""
    senha_hash = gerar_hash_senha(_senha_demo())
    ids = [_usuario(db, nome, email, senha_hash) for nome, email in CONTAS]
    comitente, compradores = ids[0], ids[1:]
    t = agora(db)
    criados = {}

    criados["agendado"] = _leilao(db, comitente, "Bicicleta aro 29", "Esportes e lazer", "800.00",
                                  t + timedelta(minutes=2), 5)
    _leilao(db, comitente, "Câmera analógica", "Colecionáveis", "350.00", t + timedelta(minutes=10), 10)

    andamento = _leilao(db, comitente, "Notebook 14 polegadas", "Eletrônicos", "1500.00",
                        t - timedelta(minutes=5), 20, estado="em_andamento")
    _lances(db, andamento, compradores[:2], ["1500.00", "1501.00", "1550.00"], t)
    criados["em_andamento"] = andamento

    vendido = _leilao(db, comitente, "Luminária de mesa", "Casa e decoração", "60.00",
                      t - timedelta(hours=2), 30, estado="em_andamento")
    vencedor = _lances(db, vendido, compradores, ["60.00", "65.00", "80.00"], t - timedelta(hours=1))
    db.execute(update(Leilao).where(Leilao.id == vendido).values(
        estado="vendido", lance_vencedor_id=vencedor, encerrado_em=t - timedelta(hours=1, minutes=30),
        versao=Leilao.versao + 1))
    criados["vendido"] = vendido

    sem_lances = _leilao(db, comitente, "Coleção de livros", "Livros e mídia", "120.00",
                         t - timedelta(hours=3), 30, estado="em_andamento")
    db.execute(update(Leilao).where(Leilao.id == sem_lances).values(
        estado="encerrado_sem_lances", encerrado_em=t - timedelta(hours=2, minutes=30), versao=1))
    criados["encerrado_sem_lances"] = sem_lances

    cancelado = _leilao(db, comitente, "Jaqueta de couro", "Moda", "200.00", t + timedelta(hours=1), 30)
    db.execute(update(Leilao).where(Leilao.id == cancelado).values(estado="cancelado", encerrado_em=t, versao=1))
    criados["cancelado"] = cancelado

    db.commit()
    return criados


def main() -> None:
    from app.db import SessionLocal  # so aqui: importar o modulo nao exige banco
    with SessionLocal() as db:
        popular(db)
    print("Dados de demonstração criados. Contas (senha: DEMO_PASSWORD, padrão demo1234):")
    for nome, email in CONTAS:
        print(f"  {email}  ({nome})")


if __name__ == "__main__":
    main()
