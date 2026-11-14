"""Dinheiro e formato de instantes (sem banco); relogio do banco (com TEST_DATABASE_URL)."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
import unittest

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app import dinheiro
from app.tempo import agora, iso_utc


class DinheiroTest(unittest.TestCase):
    def test_ler_aceita_ate_duas_casas_e_normaliza(self):
        self.assertEqual(dinheiro.ler("150"), Decimal("150.00"))
        self.assertEqual(dinheiro.ler(" 10.5 "), Decimal("10.50"))
        self.assertEqual(dinheiro.ler("0.01"), Decimal("0.01"))

    def test_ler_nunca_arredonda_nem_aceita_float(self):
        for invalido in ("10.999", "0", "-1.00", "abc", "", "NaN", "Infinity", "1e400", "10000000000.00"):
            with self.subTest(valor=invalido):
                with self.assertRaises(ValueError):
                    dinheiro.ler(invalido)
        with self.assertRaises(ValueError):
            dinheiro.ler(10.5)  # float nunca entra

    def test_texto_sempre_duas_casas_sem_notacao_cientifica(self):
        self.assertEqual(dinheiro.texto(Decimal("150")), "150.00")
        self.assertEqual(dinheiro.texto(Decimal("1E+3")), "1000.00")
        self.assertEqual(dinheiro.texto(Decimal("0.1") + Decimal("0.2")), "0.30")


class IsoUtcTest(unittest.TestCase):
    def test_converte_qualquer_fuso_para_utc_com_z(self):
        sp = timezone(timedelta(hours=-3))
        self.assertEqual(iso_utc(datetime(2026, 11, 14, 15, 0, tzinfo=sp)), "2026-11-14T18:00:00Z")
        self.assertEqual(iso_utc(datetime(2026, 11, 14, 18, 0, tzinfo=timezone.utc)), "2026-11-14T18:00:00Z")

    def test_instante_sem_fuso_e_erro(self):
        with self.assertRaises(ValueError):
            iso_utc(datetime(2026, 11, 14, 18, 0))


@unittest.skipUnless(os.environ.get("TEST_DATABASE_URL"), "Defina TEST_DATABASE_URL para PostgreSQL de testes")
class RelogioDoBancoTest(unittest.TestCase):
    def test_clock_timestamp_avanca_dentro_da_mesma_transacao(self):
        engine = create_engine(os.environ["TEST_DATABASE_URL"])
        self.addCleanup(engine.dispose)
        with Session(engine) as db:
            primeiro = agora(db)
            db.execute(text("SELECT pg_sleep(0.05)"))
            segundo = agora(db)  # mesma transacao: now() repetiria o valor
            self.assertIsNotNone(primeiro.tzinfo)
            self.assertGreater(segundo, primeiro)
