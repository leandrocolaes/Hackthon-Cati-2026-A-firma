"""Restricoes reais em PostgreSQL; requer TEST_DATABASE_URL de um banco de testes.

Cria e remove apenas um schema aleatorio proprio, nunca tabelas do schema public.
Executar em backend/: python -m unittest discover -s tests -v
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
from pathlib import Path
import subprocess
import sys
import unittest
from uuid import uuid4

from sqlalchemy import create_engine, delete, insert, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateSchema, DropSchema

# Importar os modelos nao abre conexao. O destino real dos testes e separado.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://unused:unused@localhost/unused")
from app.models import FotoItem, Item, Lance, Leilao, Participante, Sessao, TentativaLance, Usuario


@unittest.skipUnless(os.environ.get("TEST_DATABASE_URL"), "Defina TEST_DATABASE_URL para PostgreSQL de testes")
class DominioPostgreSQLTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        url = make_url(os.environ["TEST_DATABASE_URL"])
        if url.drivername != "postgresql+psycopg":
            raise ValueError("Use TEST_DATABASE_URL com driver postgresql+psycopg")
        cls.schema = "teste_dominio_" + uuid4().hex
        cls.admin = create_engine(url)
        with cls.admin.begin() as conn:
            conn.execute(CreateSchema(cls.schema))
        cls.addClassCleanup(cls.limpar_schema)
        cls.url = url.update_query_dict({"options": "-csearch_path=" + cls.schema})
        cls.engine = create_engine(cls.url)
        cls.addClassCleanup(cls.engine.dispose)
        cls.migrar("upgrade", "0001_usuarios_sessoes")
        # Simula dados existentes antes da segunda migracao.
        with cls.engine.begin() as conn:
            cls.usuario_id = conn.execute(insert(Usuario).values(
                nome="Ana", email="ana@example.com", senha_hash="hash-apenas-fixture"
            ).returning(Usuario.id)).scalar_one()
            conn.execute(insert(Sessao).values(
                usuario_id=cls.usuario_id, token_hash="a" * 64,
                expira_em=datetime.now(timezone.utc) + timedelta(hours=2),
            ))
        cls.migrar("upgrade", "head")
        cls.migrar("upgrade", "head")

    @classmethod
    def limpar_schema(cls):
        try:
            with cls.admin.begin() as conn:
                conn.execute(DropSchema(cls.schema, cascade=True))
        finally:
            cls.admin.dispose()

    @classmethod
    def migrar(cls, *args):
        env = dict(os.environ, DATABASE_URL=cls.url.render_as_string(hide_password=False))
        result = subprocess.run(
            [sys.executable, "-m", "alembic", *args],
            cwd=Path(__file__).resolve().parents[1], env=env,
            capture_output=True, text=True,
        )
        if result.returncode:
            # Nao imprimir ambiente, URL nem traceback que possa conter credenciais.
            raise AssertionError("Alembic falhou no schema isolado; examine o comando no banco de testes")

    def setUp(self):
        self.conn = self.engine.connect()
        self.tx = self.conn.begin()
        self.addCleanup(self.conn.close)
        self.addCleanup(self.tx.rollback)

    def inserir(self, model, **values):
        return self.conn.execute(insert(model).values(**values).returning(model.id)).scalar_one()

    def recusa(self, statement, constraint=None):
        with self.assertRaises(IntegrityError) as captured:
            with self.conn.begin_nested():
                self.conn.execute(statement)
        if constraint:
            self.assertEqual(captured.exception.orig.diag.constraint_name, constraint)

    def criar_leilao(self):
        item_id = self.inserir(Item, usuario_id=self.usuario_id, nome="Livro",
                               descricao="Livro de demonstracao", categoria="Outros")
        inicio = datetime.now(timezone.utc) + timedelta(minutes=1)
        leilao_id = self.inserir(
            Leilao, item_id=item_id, comitente_id=self.usuario_id,
            preco_inicial=Decimal("1.10"), preco_atual=Decimal("1.10"),
            inicio=inicio, termino_original=inicio + timedelta(minutes=3),
            termino_vigente=inicio + timedelta(minutes=3),
        )
        return item_id, leilao_id

    def test_migracao_preserva_contas_sessoes_e_corresponde_aos_modelos(self):
        self.assertEqual(self.conn.execute(select(Usuario.email)).scalar_one(), "ana@example.com")
        self.assertEqual(self.conn.execute(select(Sessao.usuario_id)).scalar_one(), self.usuario_id)
        self.migrar("check")

    def test_email_normalizado_unico_e_exclusao_bloqueada(self):
        self.recusa(insert(Usuario).values(nome="Outro", email="ana@example.com", senha_hash="fixture"))
        self.recusa(insert(Usuario).values(nome="Outro", email=" ANA@example.com ", senha_hash="fixture"),
                    "ck_usuarios_email_normalizado")
        self.recusa(delete(Usuario).where(Usuario.id == self.usuario_id))

    def test_fotos_e_apelidos_nao_duplicam(self):
        item_id, leilao_id = self.criar_leilao()
        self.inserir(FotoItem, item_id=item_id, url="https://example.com/foto", ordem=0)
        self.recusa(insert(FotoItem).values(item_id=item_id, url="https://example.com/outra", ordem=0),
                    "uq_fotos_itens_item_ordem")
        self.recusa(insert(FotoItem).values(item_id=item_id, url="https://example.com/outra", ordem=-1),
                    "ck_fotos_itens_ordem")
        self.inserir(Participante, leilao_id=leilao_id, usuario_id=self.usuario_id, numero=1)
        self.recusa(insert(Participante).values(leilao_id=leilao_id, usuario_id=self.usuario_id, numero=2),
                    "uq_participantes_leilao_usuario")
        outro = self.inserir(Usuario, nome="Bruno", email="bruno@example.com", senha_hash="fixture")
        self.recusa(insert(Participante).values(leilao_id=leilao_id, usuario_id=outro, numero=1),
                    "uq_participantes_leilao_numero")

    def test_item_tem_no_maximo_um_leilao_ativo(self):
        item_id, leilao_id = self.criar_leilao()
        values = dict(self.conn.execute(select(Leilao.__table__)).mappings().one())
        for field in ("id", "criado_em"):
            values.pop(field)
        self.recusa(insert(Leilao).values(**values), "uq_leiloes_item_ativo")
        self.conn.execute(update(Leilao).where(Leilao.id == leilao_id).values(
            estado="cancelado", encerrado_em=datetime.now(timezone.utc)))
        self.inserir(Leilao, **values)
        self.recusa(delete(Item).where(Item.id == item_id))

    def test_estado_agenda_preco_e_resultado_coerentes(self):
        _, leilao_id = self.criar_leilao()
        statement = update(Leilao).where(Leilao.id == leilao_id)
        self.recusa(statement.values(estado="inexistente"), "ck_leiloes_estado")
        self.recusa(statement.values(preco_atual=Decimal("0.10")), "ck_leiloes_preco_atual")
        self.recusa(statement.values(termino_original=Leilao.inicio), "ck_leiloes_termino_original")
        self.recusa(statement.values(termino_vigente=Leilao.inicio), "ck_leiloes_termino_vigente")
        self.recusa(statement.values(estado="cancelado"), "ck_leiloes_encerramento")
        self.recusa(statement.values(estado="vendido", encerrado_em=datetime.now(timezone.utc)),
                    "ck_leiloes_vencedor")
        lance_id = self.inserir(Lance, leilao_id=leilao_id, usuario_id=self.usuario_id, valor=Decimal("1.10"))
        self.conn.execute(statement.values(estado="vendido", lance_vencedor_id=lance_id,
                                          lider_id=self.usuario_id, encerrado_em=datetime.now(timezone.utc)))
        self.recusa(delete(Lance).where(Lance.id == lance_id), "fk_leiloes_lance_vencedor")
        self.recusa(insert(Lance).values(leilao_id=leilao_id, usuario_id=self.usuario_id, valor=0),
                    "ck_lances_valor")

    def test_tentativas_completas_e_chave_unica_entre_leiloes(self):
        _, primeiro = self.criar_leilao()
        _, segundo = self.criar_leilao()
        chave = uuid4()
        values = dict(usuario_id=self.usuario_id, leilao_id=primeiro, chave=chave,
                      valor_solicitado=Decimal("0.10"), situacao="recusada", status_http=409,
                      resposta_original={"codigo": "abaixo_do_minimo", "minimo": "1.10"})
        self.inserir(TentativaLance, **values)
        self.recusa(insert(TentativaLance).values(**dict(values, leilao_id=segundo)),
                    "uq_tentativas_lance_usuario_chave")
        self.recusa(insert(TentativaLance).values(**dict(values, chave=uuid4(), situacao="pendente")),
                    "ck_tentativas_lance_situacao")
        self.recusa(insert(TentativaLance).values(**dict(values, chave=uuid4(), resposta_original=None)))
        lance_id = self.inserir(Lance, leilao_id=primeiro, usuario_id=self.usuario_id, valor=Decimal("1.10"))
        accepted = dict(values, chave=uuid4(), lance_id=lance_id, situacao="aceita", status_http=201,
                        resposta_original={"lance_id": lance_id})
        self.inserir(TentativaLance, **accepted)
        self.recusa(insert(TentativaLance).values(**dict(accepted, chave=uuid4())),
                    "uq_tentativas_lance_lance")
        row = self.conn.execute(select(TentativaLance.__table__).where(TentativaLance.chave == chave)).mappings().one()
        self.assertEqual(row["resposta_original"], values["resposta_original"])
        self.assertEqual(row["valor_solicitado"], Decimal("0.10"))
        self.assertIsNotNone(row["criado_em"].tzinfo)


if __name__ == "__main__":
    unittest.main()
