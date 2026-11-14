"""Contrato de configuracao: sem banco, rede ou leitura do .env real nos testes."""

from decimal import Decimal
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app.config import Configuracoes, obter_configuracoes

URL_TESTE = "postgresql+psycopg://teste:segredo-apenas-fixture@localhost/teste"


class ConfiguracoesTest(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"DATABASE_URL": URL_TESTE}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        obter_configuracoes.cache_clear()
        self.addCleanup(obter_configuracoes.cache_clear)

    def config(self, **valores):
        return Configuracoes(_env_file=None, **valores)

    def test_padrao_temporario_sem_fotos_e_preserva_dinheiro_decimal(self):
        config = self.config()
        self.assertEqual(config.fotos_minimas, 0)  # TEMPORARIO ate o F11; depois 3
        self.assertEqual(config.preco_inicial_minimo, Decimal("1.00"))
        self.assertIsInstance(config.preco_inicial_minimo, Decimal)
        self.assertEqual(config.foto_maxima_bytes, 5242880)

    def test_zero_fotos_e_opcao_explicita_da_versao_minima(self):
        self.assertEqual(self.config(ITEM_MIN_PHOTOS=0).fotos_minimas, 0)
        self.assertEqual(self.config(ITEM_MIN_PHOTOS=0, ITEM_MAX_PHOTOS=0).fotos_maximas, 0)
        with self.assertRaises(ValidationError):
            self.config(ITEM_MIN_PHOTOS=-1)
        with self.assertRaises(ValidationError):
            self.config(ITEM_MIN_PHOTOS=4, ITEM_MAX_PHOTOS=3)

    def test_intervalos_invertidos_sao_recusados(self):
        for valores in (
            {"ITEM_NAME_MIN_LENGTH": 20, "ITEM_NAME_MAX_LENGTH": 10},
            {"ITEM_DESCRIPTION_MIN_LENGTH": 20, "ITEM_DESCRIPTION_MAX_LENGTH": 10},
            {"AUCTION_MIN_ADVANCE_SECONDS": 120, "AUCTION_MAX_ADVANCE_SECONDS": 60},
            {"AUCTION_MIN_DURATION_SECONDS": 120, "AUCTION_MAX_DURATION_SECONDS": 60},
        ):
            with self.subTest(valores=valores), self.assertRaises(ValidationError):
                self.config(**valores)

    def test_configuracao_nao_ultrapassa_colunas_do_banco(self):
        for valores in ({"ITEM_NAME_MAX_LENGTH": 101}, {"ITEM_DESCRIPTION_MAX_LENGTH": 2001}):
            with self.subTest(valores=valores), self.assertRaises(ValidationError):
                self.config(**valores)

    def test_valores_nao_positivos_ou_nao_inteiros_sao_recusados(self):
        for valores in (
            {"SESSION_IDLE_MINUTES": 0}, {"BID_INCREMENT_CENTS": -1},
            {"PHOTO_MAX_BYTES": 0}, {"AUCTION_EXTENSION_SECONDS": 0},
            {"BID_INCREMENT_CENTS": "1.5"},
        ):
            with self.subTest(valores=valores), self.assertRaises(ValidationError):
                self.config(**valores)

    def test_dinheiro_invalido_nao_e_arredondado_silenciosamente(self):
        for valor in ("NaN", "Infinity", "0", "0.001", "10000000000.00"):
            with self.subTest(valor=valor), self.assertRaises(ValidationError):
                self.config(AUCTION_MIN_START_PRICE=valor)

    def test_listas_usam_os_separadores_existentes_no_env(self):
        os.environ.update(CATEGORIES="Casa e decoração | Outros", PHOTO_ALLOWED_MIME_TYPES="image/jpeg, image/png")
        config = self.config()
        self.assertEqual(config.categorias, ("Casa e decoração", "Outros"))
        self.assertEqual(config.foto_tipos_permitidos, ("image/jpeg", "image/png"))
        for valor in ("", "Outros|", "Outros|Outros"):
            with self.subTest(valor=valor), self.assertRaises(ValidationError):
                self.config(CATEGORIES=valor)

    def test_ambiente_tem_prioridade_sobre_dotenv_e_extras_do_compose_nao_falham(self):
        with tempfile.TemporaryDirectory() as tmp:
            arq = Path(tmp) / ".env"
            arq.write_text("SESSION_IDLE_MINUTES=30\nITEM_MIN_PHOTOS=0\nPOSTGRES_DB=teste\nHTTP_PORT=8080\n", encoding="utf-8")
            os.environ["SESSION_IDLE_MINUTES"] = "45"
            config = Configuracoes(_env_file=arq)
            self.assertEqual(config.sessao_inatividade_minutos, 45)
            self.assertEqual(config.fotos_minimas, 0)

    def test_dotenv_da_raiz_independe_da_pasta_do_terminal(self):
        # Copia apenas config.py para uma arvore descartavel, sem tocar no .env real.
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            app = raiz / "backend" / "app"
            app.mkdir(parents=True)
            (app / "__init__.py").write_text("")
            shutil.copyfile(Path(__file__).resolve().parents[1] / "app" / "config.py", app / "config.py")
            (raiz / ".env").write_text(f"DATABASE_URL={URL_TESTE}\nITEM_MIN_PHOTOS=0\n", encoding="utf-8")
            outra_pasta = raiz / "outro-diretorio"
            outra_pasta.mkdir()
            resultado = subprocess.run(
                [sys.executable, "-c", "from app.config import obter_configuracoes; assert obter_configuracoes().fotos_minimas == 0; print('ok')"],
                cwd=outra_pasta, env={"PYTHONPATH": str(raiz / "backend")},
                capture_output=True, text=True,
            )
            self.assertEqual(resultado.returncode, 0, resultado.stderr)
            self.assertEqual(resultado.stdout.strip(), "ok")

    def test_cache_carrega_uma_vez_e_objeto_nao_muda(self):
        with patch.object(Configuracoes, "model_config", dict(Configuracoes.model_config, env_file=None)):
            primeiro = obter_configuracoes()
            os.environ["ITEM_MIN_PHOTOS"] = "5"
            self.assertIs(primeiro, obter_configuracoes())
            self.assertEqual(primeiro.fotos_minimas, 0)
            with self.assertRaises(ValidationError):
                primeiro.fotos_minimas = 5
            obter_configuracoes.cache_clear()
            self.assertEqual(obter_configuracoes().fotos_minimas, 5)

    def test_url_invalida_nao_vaza_credencial_no_erro_ou_repr(self):
        config = self.config()
        self.assertNotIn("segredo-apenas-fixture", repr(config))
        for url in ("sqlite:///teste", "url-invalida-com-segredo-apenas-fixture", "postgresql+psycopg://localhost"):
            with self.subTest(url=url), self.assertRaises(ValidationError) as captured:
                self.config(DATABASE_URL=url)
            self.assertNotIn("segredo-apenas-fixture", str(captured.exception))
            self.assertIn("DATABASE_URL", str(captured.exception))


if __name__ == "__main__":
    unittest.main()
