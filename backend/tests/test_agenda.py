"""Abertura e fechamento automaticos, inclusive apos parada (RF17, RF18)."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import threading

from tests.apoio import PRECISA_BANCO, TesteAPI  # primeiro: define DATABASE_URL ficticia

from app.config import Configuracoes, obter_configuracoes  # noqa: E402
from app.main import app  # noqa: E402
from app.servicos import agenda  # noqa: E402

CFG_SEM_FOTOS = Configuracoes(_env_file=None, ITEM_MIN_PHOTOS=0)


@PRECISA_BANCO
class AgendaTest(TesteAPI):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        app.dependency_overrides[obter_configuracoes] = lambda: CFG_SEM_FOTOS
        cls.ana = None

    def criar(self) -> int:
        if self.ana is None:
            type(self).ana = self.cadastrar_e_entrar()
        inicio = (datetime.now(timezone.utc) + timedelta(seconds=120)).isoformat()
        r = self.ana.post("/api/leiloes", json={
            "nome": "Livro", "descricao": "Livro em bom estado", "categoria": "Outros",
            "preco_inicial": "10.00", "inicio": inicio, "duracao_segundos": 180, "fotos": []})
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["id"]

    def ciclo(self):
        with self.banco.Sessao() as db:
            return agenda.ciclo(db)

    def estado(self, leilao_id):
        return self.banco.sql("SELECT estado, lance_vencedor_id, encerrado_em, versao FROM leiloes WHERE id=:id",
                              id=leilao_id).one()

    def mover(self, leilao_id, inicio, termino, estado=None):
        """Desloca os horarios (em segundos a partir de agora) para simular o tempo passando."""
        self.banco.sql(
            "UPDATE leiloes SET inicio = clock_timestamp() + make_interval(secs => :i), "
            "termino_original = clock_timestamp() + make_interval(secs => :t), "
            "termino_vigente = clock_timestamp() + make_interval(secs => :t), "
            "estado = coalesce(:e, estado) WHERE id = :id", i=inicio, t=termino, e=estado, id=leilao_id)

    def lance_direto(self, leilao_id, usuario_id, valor):
        """Lance gravado direto no banco: este arquivo testa o fechamento, nao a rota de lance."""
        self.banco.sql("INSERT INTO lances (leilao_id, usuario_id, valor) VALUES (:l, :u, :v)",
                       l=leilao_id, u=usuario_id, v=valor)
        self.banco.sql("UPDATE leiloes SET preco_atual = :v, lider_id = :u WHERE id = :l",
                       l=leilao_id, u=usuario_id, v=valor)

    def test_abre_no_horario_e_versao_sobe(self):
        leilao = self.criar()
        self.ciclo()
        self.assertEqual(self.estado(leilao).estado, "agendado")  # inicio ainda no futuro
        versao = self.estado(leilao).versao
        self.mover(leilao, inicio=-1, termino=60)
        abertos, _ = self.ciclo()
        self.assertIn(leilao, abertos)
        self.assertEqual(self.estado(leilao).estado, "em_andamento")
        self.assertEqual(self.estado(leilao).versao, versao + 1)

    def test_fecha_sem_lances_e_nao_duplica(self):
        leilao = self.criar()
        self.mover(leilao, inicio=-60, termino=0, estado="em_andamento")
        _, fechados = self.ciclo()
        self.assertEqual(fechados.get(leilao), "encerrado_sem_lances")
        e = self.estado(leilao)
        self.assertIsNone(e.lance_vencedor_id)
        self.assertIsNotNone(e.encerrado_em)
        self.ciclo()  # fechar de novo nao muda nada
        self.assertEqual(self.estado(leilao).versao, e.versao)

    def test_fecha_vendido_com_o_maior_lance(self):
        leilao = self.criar()
        bruno, carla = self.cadastrar_e_entrar(), self.cadastrar_e_entrar()
        self.mover(leilao, inicio=-60, termino=60, estado="em_andamento")
        for c, v in ((bruno, "10.00"), (carla, "15.00"), (bruno, "16.00")):
            self.lance_direto(leilao, c.usuario_id, v)
        self.mover(leilao, inicio=-60, termino=0)
        self.ciclo()
        e = self.estado(leilao)
        self.assertEqual(e.estado, "vendido")
        valor = self.banco.sql("SELECT valor FROM lances WHERE id=:id", id=e.lance_vencedor_id).scalar_one()
        self.assertEqual(str(valor), "16.00")

    def test_parada_longa_abre_e_fecha_na_mesma_volta(self):
        """Sistema fora do ar durante TODO o leilao (RF18): uma volta resolve."""
        leilao = self.criar()
        self.mover(leilao, inicio=-600, termino=-300)
        abertos, fechados = self.ciclo()
        self.assertIn(leilao, abertos)
        self.assertEqual(fechados.get(leilao), "encerrado_sem_lances")

    def test_prorrogado_nao_fecha_no_termino_original(self):
        leilao = self.criar()
        self.mover(leilao, inicio=-600, termino=60, estado="em_andamento")
        self.banco.sql("UPDATE leiloes SET termino_original = clock_timestamp() - interval '1 minute' "
                       "WHERE id=:id", id=leilao)
        self.ciclo()
        self.assertEqual(self.estado(leilao).estado, "em_andamento")

    def test_dois_workers_ao_mesmo_tempo_fecham_uma_vez(self):
        leiloes = [self.criar() for _ in range(5)]
        for l in leiloes:
            self.mover(l, inicio=-60, termino=0, estado="em_andamento")
        barreira = threading.Barrier(2)

        def worker():
            barreira.wait()
            with self.banco.Sessao() as db:
                return agenda.fechar_vencidos(db)
        with ThreadPoolExecutor(2) as ex:
            resultados = list(ex.map(lambda _: worker(), range(2)))
        fechados = [l for r in resultados for l in r]
        self.assertEqual(sorted(fechados), sorted(leiloes))  # cada leilao fechado uma unica vez
        versoes = self.banco.sql("SELECT versao FROM leiloes WHERE id = ANY(:ids)", ids=leiloes).scalars().all()
        self.assertTrue(all(v == 1 for v in versoes))
