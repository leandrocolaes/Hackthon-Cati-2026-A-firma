"""RF25: modo espectador por HTTP (sem login, sem participacao, sem dados privados)."""

from uuid import uuid4

from tests.apoio import PRECISA_BANCO, TesteLeilao  # primeiro: define DATABASE_URL ficticia

CAMPOS_PUBLICOS = {
    "id", "versao", "estado", "server_time", "inicio", "termino_original", "termino_vigente", "hard_end",
    "prorrogacao_esgotada", "preco_atual", "lance_minimo", "lider", "total_lances", "ultimos_lances",
    "resultado", "espectador",
}


@PRECISA_BANCO
class EspectadorTest(TesteLeilao):
    def setUp(self):
        self.ana = self.cadastrar_e_entrar(nome="Ana Comitente")
        self.bruno = self.cadastrar_e_entrar(nome="Bruno Comprador")
        self.leilao = self.novo_leilao(self.ana)
        self.entrar(self.bruno, self.leilao)
        self.abrir_agora(self.leilao)
        r = self.bruno.post(f"/api/leiloes/{self.leilao}/lances", json={"valor": "100.00", "chave": str(uuid4())})
        self.assertEqual(r.status_code, 201, r.text)

    def participantes(self) -> int:
        return self.banco.sql("SELECT count(*) FROM participantes WHERE leilao_id=:l", l=self.leilao).scalar_one()

    def test_visitante_sem_login_ve_o_estado_permitido(self):
        antes = self.participantes()
        r = self.cliente().get(f"/api/leiloes/{self.leilao}/espectador")
        self.assertEqual(r.status_code, 200, r.text)
        s = r.json()
        self.assertEqual(set(s), CAMPOS_PUBLICOS)
        self.assertEqual((s["preco_atual"], s["lance_minimo"], s["total_lances"]), ("100.00", "105.00", 1))
        self.assertEqual(s["lider"], {"apelido": "Participante 1"})
        self.assertEqual(set(s["ultimos_lances"][0]), {"apelido", "valor", "criado_em"})
        self.assertEqual(self.participantes(), antes)  # nao virou participante

    def test_nao_expoe_dados_privados_nem_ids_internos(self):
        texto = self.cliente().get(f"/api/leiloes/{self.leilao}/espectador").text
        for proibido in (self.ana.email, self.bruno.email, "Bruno", "Ana Comitente", "participante_id",
                         "usuario_id", "meu_participante_id", "sou_comitente", "pode_dar_lance"):
            self.assertNotIn(proibido, texto)

    def test_usuario_logado_que_assiste_nao_vira_participante_nem_renova_sessao(self):
        carla = self.cadastrar_e_entrar()
        sessao = "SELECT expira_em FROM sessoes WHERE usuario_id=:u"
        antes = self.banco.sql(sessao, u=carla.usuario_id).scalar_one()
        self.assertEqual(carla.get(f"/api/leiloes/{self.leilao}/espectador").status_code, 200)
        self.assertEqual(self.banco.sql("SELECT count(*) FROM participantes WHERE usuario_id=:u",
                                        u=carla.usuario_id).scalar_one(), 0)
        self.assertEqual(self.banco.sql(sessao, u=carla.usuario_id).scalar_one(), antes)
        # Sem participacao, a sala de participante continua fechada para ela.
        self.assertEqual(carla.get(f"/api/leiloes/{self.leilao}/sala").status_code, 403)

    def test_so_leilao_em_andamento(self):
        agendado = self.novo_leilao(self.ana)
        cancelado = self.novo_leilao(self.ana)
        self.assertEqual(self.ana.post(f"/api/leiloes/{cancelado}/cancelar").status_code, 200)
        for leilao_id in (agendado, cancelado):
            r = self.cliente().get(f"/api/leiloes/{leilao_id}/espectador")
            self.assertEqual((r.status_code, r.json()["codigo"]), (409, "leilao_fora_do_estado"))
        self.assertEqual(self.cliente().get("/api/leiloes/999999/espectador").status_code, 404)
