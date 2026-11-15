"""Dados de demonstracao (RNF04): contas reaproveitadas, leiloes em todos os estados."""

from tests.apoio import PRECISA_BANCO, TesteAPI  # primeiro: define DATABASE_URL ficticia

from app import seed  # noqa: E402


@PRECISA_BANCO
class SeedTest(TesteAPI):
    def popular(self):
        with self.banco.Sessao() as db:
            return seed.popular(db)

    def test_cria_todos_os_estados_e_nao_duplica_contas(self):
        primeiro = self.popular()
        estados = {"agendado", "em_andamento", "vendido", "encerrado_sem_lances", "cancelado"}
        self.assertEqual(set(primeiro), estados | {"prorrogacao_esgotada", "vencido_por_comprador1"})
        for estado in estados:
            atual = self.banco.sql("SELECT estado FROM leiloes WHERE id=:id", id=primeiro[estado]).scalar_one()
            self.assertEqual(atual, estado)
        self.popular()
        contas = self.banco.sql("SELECT count(*) FROM usuarios WHERE email LIKE '%@demo.local'").scalar_one()
        self.assertEqual(contas, 4)

    def test_contas_entram_e_dados_aparecem_na_api(self):
        criados = self.popular()
        c = self.cliente()
        r = c.post("/api/sessao", json={"email": "comprador1@demo.local", "senha": "demo1234"})
        self.assertEqual(r.status_code, 200, r.text)
        ids = [x["id"] for x in self.cliente().get("/api/leiloes?por_pagina=100").json()["itens"]]
        self.assertIn(criados["agendado"], ids)
        self.assertIn(criados["em_andamento"], ids)
        self.assertNotIn(criados["vendido"], ids)
        sala = c.get(f"/api/leiloes/{criados['vendido']}/sala").json()  # comprador1 participou
        self.assertEqual(sala["estado"], "vendido")
        self.assertEqual(sala["resultado"]["valor"], "80.00")
        detalhe = self.cliente().get(f"/api/leiloes/{criados['em_andamento']}").json()
        self.assertEqual(len(detalhe["item"]["fotos"]), 3)
        self.assertEqual(detalhe["preco_atual"], "1600.00")

    def test_dados_da_fase_2(self):
        criados = self.popular()
        c = self.cliente()
        c.post("/api/sessao", json={"email": "comprador1@demo.local", "senha": "demo1234"})
        grupos = c.get("/api/minhas-participacoes").json()
        self.assertTrue(all(grupos[g] for g in grupos), grupos)  # os quatro grupos com algo
        self.assertIn(criados["vencido_por_comprador1"], [i["id"] for i in grupos["vencidos"]])
        sala = self.cliente().get(f"/api/leiloes/{criados['prorrogacao_esgotada']}/espectador").json()
        self.assertTrue(sala["prorrogacao_esgotada"])
        self.assertEqual(sala["lance_minimo"], "4950.00")  # faixa de R$ 50
        ref = self.cliente().get(f"/api/leiloes/{criados['agendado']}").json()["comitente"]["ref"]
        perfil = self.cliente().get(f"/api/comitentes/{ref}").json()
        self.assertGreaterEqual(perfil["encerrados"]["vendidos"], 2)
