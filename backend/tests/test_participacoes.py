"""RF27: Minhas participacoes em quatro grupos."""

from uuid import uuid4

from tests.apoio import PRECISA_BANCO, TesteLeilao  # primeiro: define DATABASE_URL ficticia


@PRECISA_BANCO
class MinhasParticipacoesTest(TesteLeilao):
    def lance(self, cliente, leilao_id, valor):
        r = cliente.post(f"/api/leiloes/{leilao_id}/lances", json={"valor": valor, "chave": str(uuid4())})
        self.assertEqual(r.status_code, 201, r.text)

    def fechar(self, leilao_id):
        """Fecha como o worker: vendido para o lider, ou encerrado sem lances."""
        self.banco.sql("""UPDATE leiloes SET encerrado_em = clock_timestamp(),
                          estado = CASE WHEN lider_id IS NULL THEN 'encerrado_sem_lances' ELSE 'vendido' END,
                          lance_vencedor_id = (SELECT id FROM lances WHERE leilao_id = leiloes.id
                                               ORDER BY valor DESC LIMIT 1)
                          WHERE id = :id""", id=leilao_id)

    def test_quatro_grupos(self):
        ana, bruno, carla = (self.cadastrar_e_entrar() for _ in range(3))
        agendado, andamento, ganhei, perdi, sem_lances, cancelado, so_comitente = (
            self.novo_leilao(ana) for _ in range(7))
        meu_proprio = self.novo_leilao(bruno)
        for leilao_id in (agendado, andamento, ganhei, perdi, sem_lances, cancelado, meu_proprio):
            self.entrar(bruno, leilao_id)
        for leilao_id in (andamento, ganhei, perdi, sem_lances):
            self.abrir_agora(leilao_id)
        self.entrar(carla, perdi)
        self.lance(bruno, ganhei, "100.00")
        self.lance(bruno, perdi, "100.00")
        self.lance(carla, perdi, "105.00")
        for leilao_id in (ganhei, perdi, sem_lances):
            self.fechar(leilao_id)
        self.assertEqual(ana.post(f"/api/leiloes/{cancelado}/cancelar").status_code, 200)

        r = bruno.get("/api/minhas-participacoes")
        self.assertEqual(r.status_code, 200, r.text)
        g = r.json()
        ids = {nome: [i["id"] for i in itens] for nome, itens in g.items()}
        self.assertEqual(ids["em_disputa"], [andamento, agendado])  # ordem do catalogo
        self.assertEqual(ids["vencidos"], [ganhei])
        self.assertEqual(set(ids["nao_vencidos"]), {perdi, sem_lances})
        self.assertEqual(ids["cancelados_encerrados"], [cancelado])
        todos = [i for itens in g.values() for i in itens]
        self.assertNotIn(so_comitente, [i["id"] for i in todos])  # nunca entrou
        self.assertNotIn(meu_proprio, [i["id"] for i in todos])  # e o comitente
        cartao = {i["id"]: i for i in todos}
        self.assertEqual(set(cartao[perdi]), {"id", "nome", "categoria", "foto_principal", "estado", "preco",
                                              "termino", "sala_acessivel"})
        self.assertEqual((cartao[perdi]["preco"], cartao[perdi]["estado"]), ("105.00", "vendido"))
        self.assertTrue(cartao[andamento]["sala_acessivel"])
        self.assertFalse(cartao[ganhei]["sala_acessivel"])

    def test_exige_login_e_nao_renova_sessao(self):
        self.assertEqual(self.cliente().get("/api/minhas-participacoes").status_code, 401)
        bruno = self.cadastrar_e_entrar()
        sql = "SELECT expira_em FROM sessoes WHERE usuario_id=:u"
        antes = self.banco.sql(sql, u=bruno.usuario_id).scalar_one()
        self.assertEqual(bruno.get("/api/minhas-participacoes").json(),
                         {"em_disputa": [], "vencidos": [], "nao_vencidos": [], "cancelados_encerrados": []})
        self.assertEqual(self.banco.sql(sql, u=bruno.usuario_id).scalar_one(), antes)
