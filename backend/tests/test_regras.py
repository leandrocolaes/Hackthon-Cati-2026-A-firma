"""Regras puras (sem banco): lance minimo, prorrogacao e impedimentos (RF10, RF14, RF15)."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
import unittest

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://unused:unused@localhost/unused")

from app.config import Configuracoes  # noqa: E402
from app.regras import edicao_permitida, espera_para_lance, hard_end, impedimento, incremento, lance_minimo, novo_termino, prorrogacao_esgotada  # noqa: E402

CFG = Configuracoes(_env_file=None)
T0 = datetime(2026, 11, 14, 18, 0, tzinfo=timezone.utc)


class RegrasTest(unittest.TestCase):
    def test_minimo_sem_lances_e_o_preco_inicial(self):
        self.assertEqual(lance_minimo(Decimal("100.00"), Decimal("100.00"), False), Decimal("100.00"))

    def test_minimo_com_lances_soma_incremento_mesmo_com_precos_iguais(self):
        self.assertEqual(lance_minimo(Decimal("100.00"), Decimal("100.00"), True), Decimal("105.00"))

    def test_incremento_em_cada_fronteira_de_faixa(self):
        casos = {
            "0.01": "1.00", "99.99": "1.00",
            "100.00": "5.00", "499.99": "5.00",
            "500.00": "10.00", "999.99": "10.00",
            "1000.00": "50.00", "4999.99": "50.00",
            "5000.00": "100.00", "24999.99": "100.00",
            "25000.00": "500.00", "1000000.00": "500.00",
        }
        for preco, esperado in casos.items():
            with self.subTest(preco=preco):
                self.assertEqual(incremento(Decimal(preco)), Decimal(esperado))

    def test_minimo_usa_a_faixa_do_preco_atual_confirmado(self):
        casos = {"99.99": "100.99", "100.00": "105.00", "499.99": "504.99", "500.00": "510.00",
                 "999.99": "1009.99", "1000.00": "1050.00", "4999.99": "5049.99", "5000.00": "5100.00",
                 "24999.99": "25099.99", "25000.00": "25500.00"}
        for atual, esperado in casos.items():
            with self.subTest(atual=atual):
                self.assertEqual(lance_minimo(Decimal("1.00"), Decimal(atual), True), Decimal(esperado))

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

    def test_exemplo_do_documento_lance_aos_9_03_leva_a_10_03(self):
        vigente = T0 + timedelta(minutes=10)
        instante = T0 + timedelta(minutes=9, seconds=3)
        self.assertEqual(novo_termino(instante, vigente, vigente, CFG), T0 + timedelta(minutes=10, seconds=3))

    def test_hard_end_e_original_mais_10_min(self):
        self.assertEqual(hard_end(T0, CFG), T0 + timedelta(minutes=10))
        self.assertFalse(prorrogacao_esgotada(T0 + timedelta(minutes=9, seconds=59), T0, CFG))
        self.assertTrue(prorrogacao_esgotada(T0 + timedelta(minutes=10), T0, CFG))

    def test_espera_entre_lances_arredonda_para_cima(self):
        self.assertIsNone(espera_para_lance(None, T0, CFG))
        self.assertEqual(espera_para_lance(T0, T0, CFG), 2)
        self.assertEqual(espera_para_lance(T0, T0 + timedelta(seconds=1.2), CFG), 1)
        self.assertIsNone(espera_para_lance(T0, T0 + timedelta(seconds=2), CFG))
        sem_limite = Configuracoes(_env_file=None, BID_MIN_INTERVAL_SECONDS=0)
        self.assertIsNone(espera_para_lance(T0, T0, sem_limite))

    def test_edicao_so_agendado_antes_do_inicio_e_sem_lances(self):
        inicio = T0 + timedelta(minutes=5)
        self.assertTrue(edicao_permitida("agendado", T0, inicio, False))
        self.assertFalse(edicao_permitida("agendado", inicio, inicio, False))  # chegou a hora
        self.assertFalse(edicao_permitida("agendado", T0, inicio, True))  # com lance
        for estado in ("em_andamento", "vendido", "encerrado_sem_lances", "cancelado"):
            self.assertFalse(edicao_permitida(estado, T0, inicio, False))

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
