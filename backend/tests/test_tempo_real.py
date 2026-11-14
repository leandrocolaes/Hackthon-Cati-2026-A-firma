"""Sala em tempo real por WebSocket com consulta de versao (RF09; docs/contratos.md)."""

import time
from uuid import uuid4

from tests.apoio import PRECISA_BANCO, TesteLeilao  # primeiro: define DATABASE_URL ficticia

from fastapi.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

from app import tempo_real  # noqa: E402
from app.config import obter_configuracoes  # noqa: E402
from app.main import app  # noqa: E402
from app.servicos import agenda  # noqa: E402


@PRECISA_BANCO
class TempoRealTest(TesteLeilao):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        tempo_real.fabrica_sessao = cls.banco.Sessao
        cls.addClassCleanup(setattr, tempo_real, "fabrica_sessao", None)

    def setUp(self):
        # UM servidor com o ciclo de vida ligado (a tarefa que acompanha as versoes).
        self.servidor = TestClient(app)
        self.servidor.__enter__()
        self.addCleanup(self.servidor.__exit__, None, None, None)

    def ws(self, cliente, leilao_id):
        """Abre o WebSocket no servidor ligado, com o cookie de sessao do cliente."""
        nome = obter_configuracoes().sessao_cookie_nome
        cabecalhos = {"cookie": f"{nome}={cliente.cookies.get(nome)}"} if cliente else {}
        return self.servidor.websocket_connect(f"/api/leiloes/{leilao_id}/ws", headers=cabecalhos)

    def esperar(self, ws, condicao, limite=6.0):
        fim = time.monotonic() + limite
        while time.monotonic() < fim:
            msg = ws.receive_json()
            self.assertEqual(msg["tipo"], "estado_leilao")
            if condicao(msg["estado"]):
                return msg["estado"]
        self.fail("a atualizacao esperada nao chegou")

    def preparar(self):
        self.ana, self.bruno, self.carla = (self.cadastrar_e_entrar() for _ in range(3))
        self.leilao = self.novo_leilao(self.ana)
        for c in (self.ana, self.bruno, self.carla):
            self.entrar(c, self.leilao)
        self.abrir_agora(self.leilao)

    def fechado_com(self, ws):
        with self.assertRaises(WebSocketDisconnect) as erro:
            ws.receive_json()
        return erro.exception.code

    def test_recusas_no_handshake(self):
        self.preparar()
        with self.ws(None, self.leilao) as ws:
            self.assertEqual(self.fechado_com(ws), 4401)
        davi = self.cadastrar_e_entrar()
        with self.ws(davi, self.leilao) as ws:
            self.assertEqual(self.fechado_com(ws), 4403)  # sem participacao
        with self.ws(davi, 999999) as ws:
            self.assertEqual(self.fechado_com(ws), 4404)

    def test_snapshot_inicial_e_personalizado(self):
        self.preparar()
        with self.ws(self.bruno, self.leilao) as wb, self.ws(self.ana, self.leilao) as wa:
            sb, sa = wb.receive_json()["estado"], wa.receive_json()["estado"]
            self.assertNotEqual(sb["meu_participante_id"], sa["meu_participante_id"])
            self.assertTrue(sb["pode_dar_lance"])
            self.assertEqual(sa["motivo_impedimento"], "lance_do_comitente")

    def test_lance_e_fechamento_pelo_worker_chegam_a_sala(self):
        self.preparar()
        with self.ws(self.carla, self.leilao) as ws:
            self.assertEqual(ws.receive_json()["estado"]["total_lances"], 0)
            r = self.bruno.post(f"/api/leiloes/{self.leilao}/lances",
                                json={"valor": "100.00", "chave": str(uuid4())})
            self.assertEqual(r.status_code, 201)
            s = self.esperar(ws, lambda s: s["total_lances"] == 1)
            self.assertEqual(s["versao"], r.json()["versao"])
            self.assertEqual(s["lance_minimo"], "101.00")
            # Fechamento feito pelo caminho do worker (outro processo na VM).
            self.banco.sql("UPDATE leiloes SET termino_vigente = clock_timestamp(), "
                           "termino_original = clock_timestamp() WHERE id=:id", id=self.leilao)
            with self.banco.Sessao() as db:
                agenda.fechar_vencidos(db)
            s = self.esperar(ws, lambda s: s["estado"] == "vendido")
            self.assertEqual(s["resultado"]["valor"], "100.00")

    def test_sessao_expirada_fecha_com_4401(self):
        self.preparar()
        with self.ws(self.carla, self.leilao) as ws:
            ws.receive_json()
            self.banco.sql("UPDATE sessoes SET expira_em = clock_timestamp() - interval '1 s' "
                           "WHERE usuario_id = :u", u=self.carla.usuario_id)
            self.bruno.post(f"/api/leiloes/{self.leilao}/lances", json={"valor": "100.00", "chave": str(uuid4())})
            self.assertEqual(self.fechado_com(ws), 4401)

    def test_assistir_nao_renova_a_sessao(self):
        self.preparar()
        antes = self.banco.sql("SELECT expira_em FROM sessoes WHERE usuario_id=:u", u=self.carla.usuario_id).scalar_one()
        with self.ws(self.carla, self.leilao) as ws:
            ws.receive_json()
        depois = self.banco.sql("SELECT expira_em FROM sessoes WHERE usuario_id=:u", u=self.carla.usuario_id).scalar_one()
        self.assertEqual(antes, depois)
