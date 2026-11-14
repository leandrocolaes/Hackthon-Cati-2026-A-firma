"""Lances simultaneos de verdade (RF11, RF12, RF18): threads com conexoes separadas,
liberadas no mesmo instante. E o que a banca faz na demo."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import threading
import time
from uuid import uuid4

from tests.apoio import PRECISA_BANCO, TesteLeilao  # primeiro: define DATABASE_URL ficticia

from app.erros import ErroApi  # noqa: E402
from app.servicos import agenda  # noqa: E402
from app.servicos.lances import dar_lance  # noqa: E402

N = 15


@PRECISA_BANCO
class ConcorrenciaTest(TesteLeilao):
    def preparar(self, n=N, termina_em_seg=300):
        leilao = self.novo_leilao(self.cadastrar_e_entrar())
        pessoas = []
        for _ in range(n):
            c = self.cadastrar_e_entrar()
            self.entrar(c, leilao)
            sessao = self.banco.sql("SELECT id FROM sessoes WHERE usuario_id=:u", u=c.usuario_id).scalar_one()
            pessoas.append((c.usuario_id, sessao))
        self.abrir_agora(leilao, termina_em_seg)
        return leilao, pessoas

    def lance(self, leilao, usuario_id, sessao_id, valor, chave=None):
        with self.banco.Sessao() as db:
            try:
                return dar_lance(db, self.cfg, leilao, usuario_id, sessao_id, chave or uuid4(), Decimal(valor))
            except ErroApi as e:
                return e

    def simultaneo(self, chamadas):
        barreira = threading.Barrier(len(chamadas))

        def rodar(f):
            barreira.wait()
            return f()
        with ThreadPoolExecutor(len(chamadas)) as ex:
            return list(ex.map(rodar, chamadas))

    def invariantes(self, leilao):
        lances = self.banco.sql("SELECT usuario_id, valor FROM lances WHERE leilao_id=:id ORDER BY id",
                                id=leilao).all()
        for anterior, atual in zip(lances, lances[1:]):
            self.assertGreaterEqual(atual.valor, anterior.valor + Decimal("1.00"))
            self.assertNotEqual(atual.usuario_id, anterior.usuario_id)
        if lances:
            preco, lider = self.banco.sql("SELECT preco_atual, lider_id FROM leiloes WHERE id=:id", id=leilao).one()
            self.assertEqual((preco, lider), (lances[-1].valor, lances[-1].usuario_id))
        return lances

    def test_mesmo_valor_ao_mesmo_tempo_so_um_aceito(self):
        leilao, ps = self.preparar()
        rs = self.simultaneo([lambda u=u, s=s: self.lance(leilao, u, s, "100.00") for u, s in ps])
        self.assertEqual(sum(r.status == 201 for r in rs), 1)
        for r in rs:
            if r.status != 201:
                self.assertEqual(r.corpo["codigo"], "lance_abaixo_do_minimo")
                self.assertEqual(r.corpo["detalhes"]["lance_minimo"], "105.00")  # ja o novo minimo (faixa R$ 100-499,99: +R$ 5,00)
        self.assertEqual(len(self.invariantes(leilao)), 1)

    def test_rajadas_mantem_invariantes(self):
        leilao, ps = self.preparar()
        for rodada in range(5):
            base = 100 + rodada * 20
            self.simultaneo([lambda u=u, s=s, i=i: self.lance(leilao, u, s, f"{base + i}.00")
                             for i, (u, s) in enumerate(ps)])
        self.assertGreater(len(self.invariantes(leilao)), 1)

    def test_clique_duplo_em_paralelo_cria_um_lance(self):
        leilao, ps = self.preparar(n=1)
        u, s = ps[0]
        chave = uuid4()
        rs = self.simultaneo([lambda: self.lance(leilao, u, s, "100.00", chave)] * 10)
        self.assertTrue(all(r.status == 201 and r.corpo == rs[0].corpo for r in rs))
        self.assertEqual(len(self.invariantes(leilao)), 1)

    def test_mesma_chave_em_dois_leiloes_ao_mesmo_tempo(self):
        leilao1, ps = self.preparar(n=1)
        u, s = ps[0]
        leilao2 = self.novo_leilao(self.cadastrar_e_entrar())
        self.banco.sql("INSERT INTO participantes (leilao_id, usuario_id, numero) VALUES (:l, :u, 1)", l=leilao2, u=u)
        self.abrir_agora(leilao2)
        chave = uuid4()
        rs = self.simultaneo([lambda: self.lance(leilao1, u, s, "100.00", chave),
                              lambda: self.lance(leilao2, u, s, "100.00", chave)])
        self.assertEqual(sorted(r.status for r in rs), [201, 409])
        self.assertIn("chave_reutilizada", [r.corpo.get("codigo") for r in rs])
        self.assertEqual(self.banco.sql("SELECT count(*) FROM tentativas_lance WHERE chave=:c",
                                        c=chave).scalar_one(), 1)

    def test_fechamento_disputando_com_lances(self):
        """Nunca ha lance aceito depois do fechamento (RF18)."""
        leilao, ps = self.preparar()
        # Sem prorrogacao, para o fechamento acontecer durante a rajada.
        from app.config import Configuracoes
        self.cfg = Configuracoes(_env_file=None, ITEM_MIN_PHOTOS=0, AUCTION_EXTENSION_WINDOW_SECONDS=1,
                                 AUCTION_EXTENSION_SECONDS=1, AUCTION_EXTENSION_MAX_SECONDS=1)
        self.banco.sql("UPDATE leiloes SET termino_original = clock_timestamp() + interval '300 milliseconds', "
                       "termino_vigente = clock_timestamp() + interval '300 milliseconds' WHERE id=:id", id=leilao)
        parar = time.monotonic() + 1.5

        def em_loop(i, u, s):
            valor = 100 + i
            while time.monotonic() < parar:
                self.lance(leilao, u, s, f"{valor}.00")
                valor += 50

        def fechador():
            while time.monotonic() < parar:
                with self.banco.Sessao() as db:
                    agenda.fechar_vencidos(db)
        self.simultaneo([lambda i=i, u=u, s=s: em_loop(i, u, s) for i, (u, s) in enumerate(ps[:5])] + [fechador])
        estado, fim, vencedor = self.banco.sql(
            "SELECT estado, termino_vigente, lance_vencedor_id FROM leiloes WHERE id=:id", id=leilao).one()
        self.assertIn(estado, ("vendido", "encerrado_sem_lances"))
        depois = self.banco.sql("SELECT count(*) FROM lances WHERE leilao_id=:id AND criado_em >= :fim",
                                id=leilao, fim=fim).scalar_one()
        self.assertEqual(depois, 0)
        if self.invariantes(leilao):
            maior = self.banco.sql("SELECT id FROM lances WHERE leilao_id=:id ORDER BY valor DESC, id LIMIT 1",
                                   id=leilao).scalar_one()
            self.assertEqual(vencedor, maior)
