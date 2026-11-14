"""RF13: no maximo um lance a cada 2 s por participante e por leilao (relogio do servidor)."""

from uuid import uuid4

from tests.apoio import PRECISA_BANCO, TesteLeilao  # primeiro: define DATABASE_URL ficticia

from app.config import Configuracoes, obter_configuracoes  # noqa: E402
from app.main import app  # noqa: E402


@PRECISA_BANCO
class LimiteDeLancesTest(TesteLeilao):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cfg = Configuracoes(_env_file=None, ITEM_MIN_PHOTOS=0, BID_MIN_INTERVAL_SECONDS=2)
        app.dependency_overrides[obter_configuracoes] = lambda: cls.cfg

    def setUp(self):
        self.ana = self.cadastrar_e_entrar(nome="Ana")
        self.bruno = self.cadastrar_e_entrar(nome="Bruno")
        self.carla = self.cadastrar_e_entrar(nome="Carla")
        self.leilao = self.novo_leilao(self.ana)
        for c in (self.bruno, self.carla):
            self.entrar(c, self.leilao)
        self.abrir_agora(self.leilao)

    def lance(self, cliente, valor, leilao=None, chave=None):
        return cliente.post(f"/api/leiloes/{leilao or self.leilao}/lances",
                            json={"valor": valor, "chave": str(chave or uuid4())})

    def passar_intervalo(self, cliente):
        """Atalho de teste: envelhece as tentativas em vez de dormir 2 s."""
        self.banco.sql("UPDATE tentativas_lance SET criado_em = criado_em - interval '2 seconds' "
                       "WHERE usuario_id = :u", u=cliente.usuario_id)

    def tentativas(self, cliente) -> int:
        return self.banco.sql("SELECT count(*) FROM tentativas_lance WHERE usuario_id = :u",
                              u=cliente.usuario_id).scalar_one()

    def test_segundo_lance_em_menos_de_2s_e_recusado_com_tempo_restante(self):
        self.assertEqual(self.lance(self.bruno, "100.00").status_code, 201)
        self.assertEqual(self.lance(self.carla, "105.00").status_code, 201)  # outro usuario: livre
        r = self.lance(self.bruno, "110.00")
        self.assertEqual(r.status_code, 429, r.text)
        self.assertEqual(r.json()["codigo"], "lance_muito_rapido")
        self.assertIn(r.json()["detalhes"]["segundos_restantes"], (1, 2))
        self.assertIn("Aguarde", r.json()["mensagem"])
        self.assertEqual(self.tentativas(self.bruno), 1)  # a recusa por frequencia nao e gravada

    def test_depois_do_intervalo_valem_as_regras_de_sempre(self):
        self.assertEqual(self.lance(self.bruno, "100.00").status_code, 201)
        self.passar_intervalo(self.bruno)
        r = self.lance(self.bruno, "110.00")  # ainda e o lider
        self.assertEqual((r.status_code, r.json()["codigo"]), (409, "lance_do_lider"))
        self.assertEqual(self.lance(self.carla, "105.00").status_code, 201)
        self.passar_intervalo(self.bruno)
        r = self.lance(self.bruno, "106.00")  # abaixo do minimo (110,00)
        self.assertEqual((r.status_code, r.json()["codigo"]), (409, "lance_abaixo_do_minimo"))
        r = self.lance(self.bruno, "110.00")  # a recusa acima tambem conta como tentativa
        self.assertEqual(r.status_code, 429)
        self.passar_intervalo(self.bruno)
        self.assertEqual(self.lance(self.bruno, "110.00").status_code, 201)

    def test_reenvio_da_mesma_tentativa_nao_e_barrado(self):
        chave = uuid4()
        r1 = self.lance(self.bruno, "100.00", chave=chave)
        r2 = self.lance(self.bruno, "100.00", chave=chave)
        self.assertEqual((r1.status_code, r2.status_code), (201, 201))
        self.assertEqual(r1.json(), r2.json())

    def test_tentativa_recusada_por_frequencia_pode_ser_reenviada_depois(self):
        self.assertEqual(self.lance(self.bruno, "100.00").status_code, 201)
        self.assertEqual(self.lance(self.carla, "105.00").status_code, 201)
        chave = uuid4()
        self.assertEqual(self.lance(self.bruno, "110.00", chave=chave).status_code, 429)
        self.passar_intervalo(self.bruno)
        self.assertEqual(self.lance(self.bruno, "110.00", chave=chave).status_code, 201)

    def test_limite_e_por_leilao(self):
        outro = self.novo_leilao(self.ana)
        self.entrar(self.bruno, outro)
        self.abrir_agora(outro)
        self.assertEqual(self.lance(self.bruno, "100.00").status_code, 201)
        self.assertEqual(self.lance(self.bruno, "100.00", leilao=outro).status_code, 201)
