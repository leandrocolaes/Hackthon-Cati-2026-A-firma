"""Lance, reenvio, prorrogacao e sala conforme docs/contratos.md (RF09-RF12, RF14-RF16)."""

from uuid import uuid4

from tests.apoio import PRECISA_BANCO, TesteLeilao  # primeiro: define DATABASE_URL ficticia


@PRECISA_BANCO
class LancesTest(TesteLeilao):
    def preparar(self, termina_em_seg=300):
        self.ana = self.cadastrar_e_entrar(nome="Ana")
        self.bruno = self.cadastrar_e_entrar(nome="Bruno")
        self.carla = self.cadastrar_e_entrar(nome="Carla")
        self.leilao = self.novo_leilao(self.ana)
        for c in (self.ana, self.bruno, self.carla):
            self.entrar(c, self.leilao)
        self.abrir_agora(self.leilao, termina_em_seg)

    def lance(self, cliente, valor, chave=None):
        return cliente.post(f"/api/leiloes/{self.leilao}/lances", json={"valor": valor, "chave": str(chave or uuid4())})

    def sala(self, cliente):
        return cliente.get(f"/api/leiloes/{self.leilao}/sala")

    def test_aceito_no_formato_do_contrato(self):
        self.preparar()
        r = self.lance(self.bruno, "100.00")  # primeiro lance pode igualar o preco inicial
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(set(r.json()), {"lance_id", "leilao_id", "valor", "versao"})
        self.assertEqual(r.json()["valor"], "100.00")
        s = self.sala(self.carla).json()
        self.assertEqual(s["lance_minimo"], "101.00")
        self.assertEqual(s["lider"]["apelido"], "Participante 2")
        self.assertEqual(s["total_lances"], 1)
        self.assertEqual(s["ultimos_lances"][0]["valor"], "100.00")
        self.assertEqual(s["versao"], r.json()["versao"])
        self.assertTrue(s["server_time"].endswith("Z"))
        self.assertNotIn("Bruno", str(s))  # nunca o nome na sala

    def test_recusas_com_codigo_e_lance_minimo(self):
        self.preparar()
        self.assertEqual(self.lance(self.bruno, "100.00").status_code, 201)
        casos = [
            (self.ana, "500.00", "lance_do_comitente"),
            (self.bruno, "500.00", "lance_do_lider"),
            (self.carla, "100.50", "lance_abaixo_do_minimo"),
        ]
        for cliente, valor, codigo in casos:
            with self.subTest(codigo=codigo):
                r = self.lance(cliente, valor)
                self.assertEqual(r.status_code, 409, r.text)
                self.assertEqual(r.json()["codigo"], codigo)
                self.assertEqual(r.json()["detalhes"]["lance_minimo"], "101.00")
        davi = self.cadastrar_e_entrar(nome="Davi")
        r = self.lance(davi, "500.00")
        self.assertEqual((r.status_code, r.json()["codigo"]), (409, "participante_ausente"))
        self.assertEqual(self.sala(davi).status_code, 403)

    def test_entrada_invalida_401_404_nao_viram_tentativa(self):
        self.preparar()
        self.assertEqual(self.lance(self.bruno, "10.001").status_code, 422)
        self.assertEqual(self.lance(self.bruno, "-5").status_code, 422)
        self.assertEqual(self.bruno.post(f"/api/leiloes/{self.leilao}/lances",
                                         json={"valor": 100.0, "chave": str(uuid4())}).status_code, 422)
        self.assertEqual(self.lance(self.cliente(), "200.00").status_code, 401)
        r = self.bruno.post("/api/leiloes/999999/lances", json={"valor": "1.00", "chave": str(uuid4())})
        self.assertEqual((r.status_code, r.json()["codigo"]), (404, "recurso_nao_encontrado"))
        total = self.banco.sql("SELECT count(*) FROM tentativas_lance WHERE leilao_id=:id", id=self.leilao).scalar_one()
        self.assertEqual(total, 0)

    def test_agendado_e_depois_do_termino_sao_recusados_mesmo_sem_worker(self):
        self.preparar()
        self.banco.sql("UPDATE leiloes SET estado='agendado', inicio = clock_timestamp() + interval '1 minute', "
                       "termino_original = clock_timestamp() + interval '5 minutes', "
                       "termino_vigente = clock_timestamp() + interval '5 minutes' WHERE id=:id", id=self.leilao)
        self.assertEqual(self.lance(self.bruno, "100.00").json()["codigo"], "leilao_fora_do_estado")
        self.abrir_agora(self.leilao, 0.05)
        import time
        time.sleep(0.1)
        r = self.lance(self.bruno, "100.00")
        self.assertEqual(r.json()["codigo"], "leilao_encerrado")
        self.assertFalse(self.sala(self.bruno).json()["pode_dar_lance"])

    def test_reenvio_devolve_original_e_chave_reutilizada(self):
        self.preparar()
        chave = uuid4()
        r1, r2 = self.lance(self.bruno, "100.00", chave), self.lance(self.bruno, "100.00", chave)
        self.assertEqual((r1.status_code, r2.status_code), (201, 201))
        self.assertEqual(r1.json(), r2.json())
        recusa = uuid4()
        r3 = self.lance(self.carla, "50.00", recusa)
        self.lance(self.carla, "150.00")           # o estado muda...
        r4 = self.lance(self.carla, "50.00", recusa)  # ...o reenvio devolve a recusa ORIGINAL
        self.assertEqual((r3.status_code, r3.json()), (r4.status_code, r4.json()))
        r5 = self.lance(self.bruno, "999.00", chave)
        self.assertEqual((r5.status_code, r5.json()["codigo"]), (409, "chave_reutilizada"))
        self.assertEqual(self.banco.sql("SELECT count(*) FROM lances WHERE leilao_id=:id",
                                        id=self.leilao).scalar_one(), 2)

    def test_sessao_expirada_e_401(self):
        self.preparar()
        self.banco.sql("UPDATE sessoes SET expira_em = clock_timestamp() - interval '1 s' WHERE usuario_id=:u",
                       u=self.bruno.usuario_id)
        self.assertEqual(self.lance(self.bruno, "100.00").status_code, 401)

    def test_prorrogacao_versao_uma_vez_e_teto(self):
        self.preparar(termina_em_seg=20)  # dentro da janela de 60 s
        versao = self.sala(self.bruno).json()["versao"]
        r = self.lance(self.bruno, "100.00")
        self.assertEqual(r.json()["versao"], versao + 1)  # preco, lider e prazo: uma operacao so
        fim, orig, n = self.banco.sql("SELECT termino_vigente, termino_original, prorrogacoes FROM leiloes "
                                      "WHERE id=:id", id=self.leilao).one()
        self.assertGreater(fim, orig)
        self.assertEqual(n, 1)
        self.banco.sql("""UPDATE leiloes SET inicio = clock_timestamp() - interval '20 minutes',
                          termino_original = clock_timestamp() - interval '9 minutes 50 seconds',
                          termino_vigente  = clock_timestamp() + interval '10 seconds' WHERE id=:id""",
                       id=self.leilao)
        self.assertEqual(self.lance(self.carla, "200.00").status_code, 201)
        n2 = self.banco.sql("SELECT prorrogacoes FROM leiloes WHERE id=:id", id=self.leilao).scalar_one()
        self.assertEqual(n2, 1)  # no teto: nao prorroga mais

    def test_sala_resultado_vendido(self):
        self.preparar()
        self.lance(self.bruno, "100.00")
        self.banco.sql("UPDATE leiloes SET termino_vigente = clock_timestamp(), "
                       "termino_original = clock_timestamp() WHERE id=:id", id=self.leilao)
        from app.servicos import agenda
        with self.banco.Sessao() as db:
            agenda.fechar_vencidos(db)
        s = self.sala(self.carla).json()
        self.assertEqual(s["estado"], "vendido")
        self.assertEqual(s["resultado"]["valor"], "100.00")
        self.assertEqual(s["resultado"]["vencedor"]["apelido"], "Participante 2")
        self.assertEqual(s["motivo_impedimento"], "leilao_encerrado")
