"""Cadastro, sessao, logout e /api/eu conforme docs/contratos.md (RF01, RF02)."""

from tests.apoio import PRECISA_BANCO, TesteAPI  # primeiro: define DATABASE_URL ficticia

from app.config import obter_configuracoes  # noqa: E402


@PRECISA_BANCO
class AutenticacaoTest(TesteAPI):
    def test_cadastro_normaliza_e_nao_devolve_senha_nem_abre_sessao(self):
        c = self.cliente()
        r = c.post("/api/usuarios", json={"nome": "  Bia  ", "email": "  Bia@Exemplo.COM ", "senha": "12345678"})
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json(), {"id": r.json()["id"], "nome": "Bia", "email": "bia@exemplo.com"})
        self.assertNotIn(obter_configuracoes().sessao_cookie_nome, c.cookies)
        hash_salvo = self.banco.sql("SELECT senha_hash FROM usuarios WHERE id=:id", id=r.json()["id"]).scalar_one()
        self.assertTrue(hash_salvo.startswith("$2"))

    def test_email_duplicado_mesmo_com_maiusculas(self):
        self.cadastrar_e_entrar(email="dup@exemplo.com")
        r = self.cliente().post("/api/usuarios", json={"nome": "X", "email": " DUP@exemplo.com", "senha": "12345678"})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["codigo"], "email_ja_cadastrado")

    def test_entrada_invalida_lista_campos_sem_devolver_valores(self):
        c = self.cliente()
        casos = [
            ({"nome": "X", "email": "a@b.co", "senha": "curta"}, "senha"),
            ({"nome": "X", "email": "a@b.co", "senha": "é" * 40}, "senha"),   # 80 bytes
            ({"nome": "X", "email": "sem-arroba", "senha": "12345678"}, "email"),
            ({"nome": "   ", "email": "a@b.co", "senha": "12345678"}, "nome"),
        ]
        for dados, campo in casos:
            with self.subTest(campo=campo, dados=dados):
                r = c.post("/api/usuarios", json=dados)
                self.assertEqual(r.status_code, 422)
                corpo = r.json()
                self.assertEqual(corpo["codigo"], "entrada_invalida")
                self.assertIn(campo, [x["campo"] for x in corpo["detalhes"]["campos"]])
                self.assertNotIn(dados["senha"], r.text)

    def test_login_mensagem_unica_e_sessao_por_cookie(self):
        self.cadastrar_e_entrar(email="login@exemplo.com", senha="correta-123")
        c = self.cliente()
        r1 = c.post("/api/sessao", json={"email": "login@exemplo.com", "senha": "errada-123"})
        r2 = c.post("/api/sessao", json={"email": "ninguem@exemplo.com", "senha": "errada-123"})
        self.assertEqual((r1.status_code, r2.status_code), (401, 401))
        self.assertEqual(r1.json(), r2.json())
        self.assertEqual(r1.json()["codigo"], "credenciais_invalidas")
        self.assertEqual(r1.json()["mensagem"], "e-mail ou senha inválidos")
        r3 = c.post("/api/sessao", json={"email": " LOGIN@exemplo.com", "senha": "correta-123"})
        self.assertEqual(r3.status_code, 200)
        self.assertEqual(r3.json()["usuario"]["email"], "login@exemplo.com")
        self.assertNotIn("token", r3.text)
        cookie = r3.headers["set-cookie"].lower()
        self.assertIn("httponly", cookie)
        self.assertIn(obter_configuracoes().sessao_cookie_nome, cookie)
        self.assertEqual(c.get("/api/eu").json()["email"], "login@exemplo.com")

    def test_sem_sessao_eu_responde_401(self):
        r = self.cliente().get("/api/eu")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["codigo"], "sessao_invalida")

    def test_varias_sessoes_e_logout_so_da_atual(self):
        a = self.cadastrar_e_entrar(email="multi@exemplo.com", senha="senha-123")
        b = self.cliente()
        b.post("/api/sessao", json={"email": "multi@exemplo.com", "senha": "senha-123"})
        self.assertEqual(a.delete("/api/sessao").status_code, 204)
        self.assertEqual(a.get("/api/eu").status_code, 401)
        self.assertEqual(b.get("/api/eu").status_code, 200)  # outro aparelho continua
        self.assertEqual(self.cliente().delete("/api/sessao").status_code, 204)  # sem sessao tambem

    def test_sessao_expirada_nao_autoriza(self):
        c = self.cadastrar_e_entrar()
        self.banco.sql("UPDATE sessoes SET expira_em = criado_em - interval '1 minute' WHERE usuario_id = :u",
                       u=c.usuario_id)
        self.assertEqual(c.get("/api/eu").status_code, 401)

    def test_get_nao_renova_a_sessao(self):
        c = self.cadastrar_e_entrar()
        antes = self.banco.sql("SELECT expira_em FROM sessoes WHERE usuario_id=:u", u=c.usuario_id).scalar_one()
        c.get("/api/eu")
        depois = self.banco.sql("SELECT expira_em FROM sessoes WHERE usuario_id=:u", u=c.usuario_id).scalar_one()
        self.assertEqual(antes, depois)

    def test_rota_inexistente_usa_formato_de_erro(self):
        r = self.cliente().get("/api/nao-existe")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["codigo"], "recurso_nao_encontrado")
