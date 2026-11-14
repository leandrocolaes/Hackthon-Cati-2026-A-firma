"""Catalogo, criacao, detalhe e participantes conforme docs/contratos.md (RF05, RF06, RF20)."""

from datetime import datetime, timedelta, timezone

from tests.apoio import PRECISA_BANCO, TesteAPI  # primeiro: define DATABASE_URL ficticia

from app.config import Configuracoes, obter_configuracoes  # noqa: E402
from app.main import app  # noqa: E402

# Versao minima: sem fotos ate o F11 (docs/contratos.md preve ITEM_MIN_PHOTOS=0 explicito).
CFG_SEM_FOTOS = Configuracoes(_env_file=None, ITEM_MIN_PHOTOS=0)


def em(segundos: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=segundos)).isoformat()


@PRECISA_BANCO
class LeiloesTest(TesteAPI):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        app.dependency_overrides[obter_configuracoes] = lambda: CFG_SEM_FOTOS

    def dados(self, **extra):
        base = {"nome": "Livro", "descricao": "Livro em bom estado", "categoria": "Outros",
                "preco_inicial": "10.00", "inicio": em(120), "duracao_segundos": 180, "fotos": []}
        return {**base, **extra}

    def criar(self, cliente, **extra) -> int:
        r = cliente.post("/api/leiloes", json=self.dados(**extra))
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()["estado"], "agendado")
        return r.json()["id"]

    def test_criar_exige_sessao(self):
        r = self.cliente().post("/api/leiloes", json=self.dados())
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["codigo"], "sessao_invalida")

    def test_criar_e_aparecer_no_catalogo_publico_e_no_detalhe(self):
        ana = self.cadastrar_e_entrar()
        leilao_id = self.criar(ana, preco_inicial="150.5")
        catalogo = self.cliente().get("/api/leiloes").json()
        self.assertEqual(set(catalogo), {"itens", "pagina", "por_pagina", "total"})
        cartao = next(c for c in catalogo["itens"] if c["id"] == leilao_id)
        self.assertEqual(cartao["preco_atual"], "150.50")
        self.assertTrue(cartao["inicio"].endswith("Z"))
        detalhe = self.cliente().get(f"/api/leiloes/{leilao_id}").json()
        self.assertEqual(detalhe["item"]["nome"], "Livro")
        self.assertEqual(detalhe["item"]["fotos"], [])
        self.assertNotIn("lances", detalhe)
        comitente = self.banco.sql("SELECT comitente_id FROM leiloes WHERE id=:id", id=leilao_id).scalar_one()
        self.assertEqual(comitente, ana.usuario_id)  # vem da sessao, nunca da tela

    def test_validacoes_devolvem_422_com_o_campo(self):
        ana = self.cadastrar_e_entrar()
        casos = [
            ({"preco_inicial": "0.50"}, "preco_inicial"),
            ({"preco_inicial": "10.999"}, "preco_inicial"),
            ({"preco_inicial": 10.5}, "preco_inicial"),
            ({"inicio": "2026-11-14T18:00:00"}, "inicio"),      # sem fuso
            ({"inicio": em(5)}, "inicio"),                       # antecedencia menor que o minimo
            ({"duracao_segundos": 10}, "duracao_segundos"),
            ({"categoria": "Inexistente"}, "categoria"),
            ({"nome": "ab"}, "nome"),
            ({"fotos": ["ref-qualquer"]}, "fotos.0"),           # sem F11, nenhuma referencia e valida
        ]
        for extra, campo in casos:
            with self.subTest(campo=campo, extra=extra):
                r = ana.post("/api/leiloes", json=self.dados(**extra))
                self.assertEqual(r.status_code, 422, r.text)
                self.assertEqual(r.json()["codigo"], "entrada_invalida")
                self.assertIn(campo, [c["campo"] for c in r.json()["detalhes"]["campos"]])

    def test_exigindo_tres_fotos_criar_sem_fotos_e_recusado(self):
        app.dependency_overrides[obter_configuracoes] = lambda: Configuracoes(_env_file=None, ITEM_MIN_PHOTOS=3)
        self.addCleanup(app.dependency_overrides.__setitem__, obter_configuracoes, lambda: CFG_SEM_FOTOS)
        r = self.cadastrar_e_entrar().post("/api/leiloes", json=self.dados())
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detalhes"]["campos"][0]["campo"], "fotos")

    def test_catalogo_ordem_estados_e_paginacao(self):
        ana = self.cadastrar_e_entrar()
        agendado_tarde = self.criar(ana, inicio=em(600))
        agendado_cedo = self.criar(ana, inicio=em(300))
        andamento = self.criar(ana)
        cancelado = self.criar(ana)
        self.banco.sql("UPDATE leiloes SET estado='em_andamento', inicio=clock_timestamp() - interval '1 s' "
                       "WHERE id=:id", id=andamento)
        self.banco.sql("UPDATE leiloes SET estado='cancelado', encerrado_em=clock_timestamp() WHERE id=:id",
                       id=cancelado)
        ids = [c["id"] for c in self.cliente().get("/api/leiloes?por_pagina=100").json()["itens"]]
        self.assertNotIn(cancelado, ids)
        self.assertLess(ids.index(andamento), ids.index(agendado_cedo))
        self.assertLess(ids.index(agendado_cedo), ids.index(agendado_tarde))
        self.assertEqual(self.cliente().get(f"/api/leiloes/{cancelado}").status_code, 200)  # detalhe continua
        for consulta in ("pagina=0", "por_pagina=0", "por_pagina=101"):
            self.assertEqual(self.cliente().get(f"/api/leiloes?{consulta}").status_code, 422)
        self.assertEqual(self.cliente().get("/api/leiloes?pagina=1&por_pagina=1").json()["por_pagina"], 1)

    def test_participantes_numeros_estaveis_e_idempotentes(self):
        ana, bruno, carla = (self.cadastrar_e_entrar() for _ in range(3))
        leilao_id = self.criar(ana)
        b = bruno.post(f"/api/leiloes/{leilao_id}/participantes").json()
        c = carla.post(f"/api/leiloes/{leilao_id}/participantes").json()
        self.assertEqual((b["numero"], c["numero"]), (1, 2))
        self.assertEqual(b["apelido"], "Participante 1")
        self.assertEqual(bruno.post(f"/api/leiloes/{leilao_id}/participantes").json(), b)
        self.assertEqual(self.cliente().post(f"/api/leiloes/{leilao_id}/participantes").status_code, 401)
        self.assertEqual(bruno.post("/api/leiloes/999999/participantes").status_code, 404)

    def test_config_publica_nao_expoe_configuracao_interna(self):
        r = self.cliente().get("/api/config-publica")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.json()), {"item", "leilao", "foto", "categorias"})
        self.assertNotIn("postgresql", r.text)
        self.assertEqual(r.json()["leilao"]["preco_inicial_minimo"], "1.00")

    def test_entradas_simultaneas_recebem_numeros_distintos(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        leilao_id = self.criar(self.cadastrar_e_entrar())
        clientes = [self.cadastrar_e_entrar() for _ in range(10)]
        barreira = threading.Barrier(len(clientes))

        def entrar(c):
            barreira.wait()  # todos no mesmo instante
            return c.post(f"/api/leiloes/{leilao_id}/participantes")
        with ThreadPoolExecutor(len(clientes)) as ex:
            respostas = list(ex.map(entrar, clientes))
        self.assertTrue(all(r.status_code == 200 for r in respostas), [r.text for r in respostas])
        self.assertEqual(sorted(r.json()["numero"] for r in respostas), list(range(1, 11)))
