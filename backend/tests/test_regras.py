"""Regras puras (sem banco): lance minimo, prorrogacao e impedimentos (RF10, RF14, RF15)."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
import unittest

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://unused:unused@localhost/unused")

from app.config import Configuracoes  # noqa: E402
from app.regras import impedimento, lance_minimo, novo_termino  # noqa: E402

CFG = Configuracoes(_env_file=None)
T0 = datetime(2026, 11, 14, 18, 0, tzinfo=timezone.utc)


class RegrasTest(unittest.TestCase):
    def test_minimo_sem_lances_e_o_preco_inicial(self):
        self.assertEqual(lance_minimo(Decimal("100.00"), Decimal("100.00"), False, CFG), Decimal("100.00"))

    def test_minimo_com_lances_soma_incremento_mesmo_com_precos_iguais(self):
        self.assertEqual(lance_minimo(Decimal("100.00"), Decimal("100.00"), True, CFG), Decimal("101.00"))

    def test_prorrogacao_so_dentro_da_janela(self):
        fim = T0 + timedelta(minutes=5)
        self.assertIsNone(novo_termino(T0, fim, fim, CFG))
        instante = fim - timedelta(seconds=20)
        self.assertEqual(novo_termino(instante, fim, fim, CFG), instante + timedelta(seconds=60))

    def test_prorrogacao_respeita_teto_acumulado(self):
        vigente = T0 + timedelta(minutes=9, seconds=50)
        instante = vigente - timedelta(seconds=5)
        self.assertEqual(novo_termino(instante, vigente, T0, CFG), T0 + timedelta(minutes=10))
        no_teto = T0 + timedelta(minutes=10)
        self.assertIsNone(novo_termino(no_teto - timedelta(seconds=1), no_teto, T0, CFG))

    def test_impedimentos(self):
        fim = T0 + timedelta(minutes=1)
        self.assertEqual(impedimento("agendado", T0, fim, 2, 1, None), "leilao_fora_do_estado")
        self.assertEqual(impedimento("em_andamento", fim, fim, 2, 1, None), "leilao_encerrado")
        self.assertEqual(impedimento("vendido", T0, fim, 2, 1, None), "leilao_encerrado")
        self.assertEqual(impedimento("em_andamento", T0, fim, 1, 1, None), "lance_do_comitente")
        self.assertEqual(impedimento("em_andamento", T0, fim, 2, 1, 2), "lance_do_lider")
        self.assertIsNone(impedimento("em_andamento", T0, fim, 2, 1, 3))


if __name__ == "__main__":
    unittest.main()
