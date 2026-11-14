"""Base dos testes de API contra PostgreSQL real (requer TEST_DATABASE_URL).

Mesmo principio de test_dominio_db.py: cria um schema aleatorio, aplica as
migracoes nele e o apaga no final; nunca toca no schema public. A API e testada
com o TestClient do FastAPI, trocando get_db por sessoes ligadas ao schema.

Importe este modulo ANTES de qualquer "app..." : app/db.py le DATABASE_URL na
importacao, e aqui definimos uma URL ficticia para isso.
"""

import os
from pathlib import Path
import subprocess
import sys
import unittest
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://unused:unused@localhost/unused")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.schema import CreateSchema, DropSchema  # noqa: E402

from app import db as modulo_db  # noqa: E402
from app.main import app  # noqa: E402

PRECISA_BANCO = unittest.skipUnless(
    os.environ.get("TEST_DATABASE_URL"), "Defina TEST_DATABASE_URL para PostgreSQL de testes"
)


class BancoDeTeste:
    """Um schema isolado com todas as migracoes aplicadas."""

    def __init__(self):
        url = make_url(os.environ["TEST_DATABASE_URL"])
        if url.drivername != "postgresql+psycopg":
            raise ValueError("Use TEST_DATABASE_URL com driver postgresql+psycopg")
        self.schema = "teste_api_" + uuid4().hex
        self.admin = create_engine(url)
        with self.admin.begin() as conn:
            conn.execute(CreateSchema(self.schema))
        self.url = url.update_query_dict({"options": "-csearch_path=" + self.schema})
        self.engine = create_engine(self.url, pool_size=20, max_overflow=20)
        self.Sessao = sessionmaker(bind=self.engine)
        env = dict(os.environ, DATABASE_URL=self.url.render_as_string(hide_password=False))
        resultado = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True,
        )
        if resultado.returncode:
            self.fechar()
            # Nao imprimir ambiente, URL nem traceback que possa conter credenciais.
            raise AssertionError("Alembic falhou no schema de teste")

    def get_db(self):
        db = self.Sessao()
        try:
            yield db
        finally:
            db.close()

    def sql(self, comando: str, **params):
        with self.engine.begin() as conn:
            return conn.execute(text(comando), params)

    def fechar(self):
        self.engine.dispose()
        with self.admin.begin() as conn:
            conn.execute(DropSchema(self.schema, cascade=True))
        self.admin.dispose()


class TesteAPI(unittest.TestCase):
    """Cada classe de teste ganha um banco isolado; cada cliente e um navegador."""

    @classmethod
    def setUpClass(cls):
        cls.banco = BancoDeTeste()
        app.dependency_overrides[modulo_db.get_db] = cls.banco.get_db
        cls.addClassCleanup(cls.banco.fechar)
        cls.addClassCleanup(app.dependency_overrides.clear)

    def cliente(self) -> TestClient:
        return TestClient(app)

    def cadastrar_e_entrar(self, nome="Ana", email=None, senha="senha-boa-1") -> TestClient:
        c = self.cliente()
        email = email or f"{uuid4().hex[:8]}@exemplo.com"
        r = c.post("/api/usuarios", json={"nome": nome, "email": email, "senha": senha})
        self.assertEqual(r.status_code, 201, r.text)
        r = c.post("/api/sessao", json={"email": email, "senha": senha})
        self.assertEqual(r.status_code, 200, r.text)
        c.usuario_id = r.json()["usuario"]["id"]
        c.email = email
        return c


class TesteLeilao(TesteAPI):
    """Base para testes que precisam de leilao em andamento (sem fotos ate o F11)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from app.config import Configuracoes, obter_configuracoes
        # RF13 desligado (0) na base: os testes antigos dao lances seguidos do mesmo usuario.
        # O limite de 2 s e testado em test_limite_lances.py.
        cls.cfg = Configuracoes(_env_file=None, ITEM_MIN_PHOTOS=0, BID_MIN_INTERVAL_SECONDS=0)
        app.dependency_overrides[obter_configuracoes] = lambda: cls.cfg

    def novo_leilao(self, comitente, preco="100.00") -> int:
        from datetime import datetime, timedelta, timezone
        inicio = (datetime.now(timezone.utc) + timedelta(seconds=120)).isoformat()
        r = comitente.post("/api/leiloes", json={
            "nome": "Bicicleta", "descricao": "Bicicleta revisada", "categoria": "Outros",
            "preco_inicial": preco, "inicio": inicio, "duracao_segundos": 300, "fotos": []})
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["id"]

    def abrir_agora(self, leilao_id: int, termina_em_seg: float = 300):
        """Coloca em andamento sem esperar o worker (atalho de teste)."""
        self.banco.sql("""UPDATE leiloes SET estado='em_andamento',
                          inicio = clock_timestamp() - interval '1 second',
                          termino_original = clock_timestamp() + make_interval(secs => :s),
                          termino_vigente  = clock_timestamp() + make_interval(secs => :s)
                          WHERE id = :id""", id=leilao_id, s=termina_em_seg)

    def entrar(self, cliente, leilao_id):
        r = cliente.post(f"/api/leiloes/{leilao_id}/participantes")
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()
