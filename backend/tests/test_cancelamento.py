"""Cancelamento conforme docs/contratos.md (RF08, RN01, HU09)."""

from concurrent.futures import ThreadPoolExecutor
import threading
from uuid import uuid4

from tests.apoio import PRECISA_BANCO, TesteLeilao  # primeiro: define DATABASE_URL ficticia


@PRECISA_BANCO
class CancelamentoTest(TesteLeilao):
    def cancelar(self, cliente, leilao_id):
        return cliente.post(f"/api/leiloes/{leilao_id}/cancelar")

    def test_agendado_cancela_e_continua_registrado(self):
        ana = self.cadastrar_e_entrar()
        leilao = self.novo_leilao(ana)
        r = self.cancelar(self.cadastrar_e_entrar(), leilao)
        self.assertEqual((r.status_code, r.json()["codigo"]), (403, "cancelamento_nao_autorizado"))
        self.assertEqual(self.cancelar(self.cliente(), leilao).status_code, 401)
        r = self.cancelar(ana, leilao)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(set(r.json()), {"id", "estado", "encerrado_em", "versao"})
        self.assertEqual(r.json()["estado"], "cancelado")
        self.assertTrue(r.json()["encerrado_em"].endswith("Z"))
        self.assertEqual(self.cliente().get(f"/api/leiloes/{leilao}").json()["estado"], "cancelado")
        ids = [c["id"] for c in self.cliente().get("/api/leiloes?por_pagina=100").json()["itens"]]
        self.assertNotIn(leilao, ids)
        r = self.cancelar(ana, leilao)
        self.assertEqual((r.status_code, r.json()["codigo"]), (409, "cancelamento_nao_permitido"))
        self.assertEqual(self.cancelar(ana, 999999).status_code, 404)

    def test_em_andamento_so_sem_lances_e_antes_do_termino(self):
        ana, bruno = self.cadastrar_e_entrar(), self.cadastrar_e_entrar()
        sem = self.novo_leilao(ana)
        self.abrir_agora(sem)
        self.assertEqual(self.cancelar(ana, sem).status_code, 200)

        com = self.novo_leilao(ana)
        self.entrar(bruno, com)
        self.abrir_agora(com)
        bruno.post(f"/api/leiloes/{com}/lances", json={"valor": "100.00", "chave": str(uuid4())})
        r = self.cancelar(ana, com)
        self.assertEqual((r.status_code, r.json()["codigo"]), (409, "cancelamento_nao_permitido"))
        self.assertIn("lances", r.json()["mensagem"])

        vencido = self.novo_leilao(ana)
        self.abrir_agora(vencido, 0)
        self.assertEqual(self.cancelar(ana, vencido).status_code, 409)

    def test_cancelamento_e_lance_simultaneos_nunca_ficam_os_dois(self):
        for _ in range(5):
            ana, bruno = self.cadastrar_e_entrar(), self.cadastrar_e_entrar()
            leilao = self.novo_leilao(ana)
            self.entrar(bruno, leilao)
            self.abrir_agora(leilao)
            barreira = threading.Barrier(2)

            def cancelar():
                barreira.wait()
                return self.cancelar(ana, leilao).status_code

            def dar_lance():
                barreira.wait()
                return bruno.post(f"/api/leiloes/{leilao}/lances",
                                  json={"valor": "100.00", "chave": str(uuid4())}).status_code
            with ThreadPoolExecutor(2) as ex:
                c, l = ex.submit(cancelar), ex.submit(dar_lance)
                status = (c.result(), l.result())
            self.assertIn(status, [(200, 409), (409, 201)])  # exatamente um dos dois venceu
            estado, lider = self.banco.sql("SELECT estado, lider_id FROM leiloes WHERE id=:id", id=leilao).one()
            self.assertFalse(estado == "cancelado" and lider is not None)
