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
        self.assertEqual(set(primeiro), {"agendado", "em_andamento", "vendido", "encerrado_sem_lances", "cancelado"})
        for estado, leilao_id in primeiro.items():
            atual = self.banco.sql("SELECT estado FROM leiloes WHERE id=:id", id=leilao_id).scalar_one()
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
        self.assertEqual(detalhe["preco_atual"], "1550.00")
