"""Envio, exibicao e uso de fotos (RF07): bytes no PostgreSQL, referencia opaca por dono."""

from datetime import datetime, timedelta, timezone

from tests.apoio import PRECISA_BANCO, TesteAPI  # primeiro: define DATABASE_URL ficticia

from app.config import Configuracoes, obter_configuracoes  # noqa: E402
from app.main import app  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 40
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 40
CFG = Configuracoes(_env_file=None, ITEM_MIN_PHOTOS=3, PHOTO_MAX_BYTES=1000)


@PRECISA_BANCO
class FotosTest(TesteAPI):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        app.dependency_overrides[obter_configuracoes] = lambda: CFG

    def enviar(self, cliente, dados=PNG, nome="foto.png", tipo="image/png"):
        return cliente.post("/api/fotos", files={"arquivo": (nome, dados, tipo)})

    def referencia(self, cliente, dados=PNG) -> str:
        r = self.enviar(cliente, dados)
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["referencia"]

    def criar(self, cliente, refs):
        inicio = (datetime.now(timezone.utc) + timedelta(seconds=120)).isoformat()
        return cliente.post("/api/leiloes", json={
            "nome": "Livro", "descricao": "Livro em bom estado", "categoria": "Outros",
            "preco_inicial": "10.00", "inicio": inicio, "duracao_segundos": 180, "fotos": refs})

    def test_envio_exige_sessao(self):
        r = self.enviar(self.cliente())
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["codigo"], "sessao_invalida")

    def test_aceita_os_tres_formatos_e_serve_publicamente(self):
        ana = self.cadastrar_e_entrar()
        for dados, tipo in ((PNG, "image/png"), (JPEG, "image/jpeg"), (WEBP, "image/webp")):
            r = self.enviar(ana, dados, tipo="application/octet-stream")  # tipo vem do conteudo
            self.assertEqual(r.status_code, 201, r.text)
            corpo = r.json()
            self.assertEqual(corpo["url"], f"/api/fotos/{corpo['referencia']}")
            foto = self.cliente().get(corpo["url"])  # visitante sem login
            self.assertEqual(foto.status_code, 200)
            self.assertEqual(foto.headers["content-type"], tipo)
            self.assertEqual(foto.content, dados)
            self.assertIn("immutable", foto.headers["cache-control"])

    def test_recusa_vazio_grande_e_formato_falso(self):
        ana = self.cadastrar_e_entrar()
        casos = [b"", PNG + b"\x00" * 1000, b"GIF89a" + b"\x00" * 40, b"<svg></svg>",
                 b"texto qualquer com nome de png"]
        for dados in casos:
            with self.subTest(tamanho=len(dados)):
                r = self.enviar(ana, dados)
                self.assertEqual(r.status_code, 422, r.text)
                self.assertEqual(r.json()["detalhes"]["campos"][0]["campo"], "arquivo")
        self.assertEqual(self.enviar(ana, PNG + b"\x00" * (1000 - len(PNG))).status_code, 201)  # no limite

    def test_sem_campo_arquivo_e_422(self):
        r = self.cadastrar_e_entrar().post("/api/fotos", files={"outro": ("a.png", PNG, "image/png")})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["codigo"], "entrada_invalida")

    def test_foto_inexistente_e_404(self):
        for ref in ("nao-existe", "x" * 300):
            r = self.cliente().get(f"/api/fotos/{ref}")
            self.assertEqual(r.status_code, 404)
            self.assertEqual(r.json()["codigo"], "recurso_nao_encontrado")

    def test_criar_leilao_com_fotos_aparece_no_catalogo_e_detalhe_em_ordem(self):
        ana = self.cadastrar_e_entrar()
        refs = [self.referencia(ana, d) for d in (JPEG, PNG, WEBP)]
        r = self.criar(ana, refs)
        self.assertEqual(r.status_code, 201, r.text)
        leilao_id = r.json()["id"]
        detalhe = self.cliente().get(f"/api/leiloes/{leilao_id}").json()
        self.assertEqual(detalhe["item"]["fotos"],
                         [{"url": f"/api/fotos/{ref}", "ordem": i} for i, ref in enumerate(refs)])
        cartao = next(c for c in self.cliente().get("/api/leiloes?por_pagina=100").json()["itens"]
                      if c["id"] == leilao_id)
        self.assertEqual(cartao["foto_principal"], f"/api/fotos/{refs[0]}")

    def test_foto_de_outro_usuario_ou_repetida_e_recusada(self):
        ana, bia = self.cadastrar_e_entrar(), self.cadastrar_e_entrar()
        minhas = [self.referencia(ana) for _ in range(2)]
        dela = self.referencia(bia)
        r = self.criar(ana, [*minhas, dela])
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detalhes"]["campos"][0]["campo"], "fotos.2")
        r = self.criar(ana, [minhas[0], minhas[0], minhas[1]])
        self.assertEqual(r.status_code, 422)

    def test_minimo_de_fotos_respeitado(self):
        ana = self.cadastrar_e_entrar()
        r = self.criar(ana, [self.referencia(ana) for _ in range(2)])
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detalhes"]["campos"][0]["campo"], "fotos")
