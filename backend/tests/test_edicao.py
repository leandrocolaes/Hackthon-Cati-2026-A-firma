"""Edicao de leilao agendado e "meus leiloes" (decisao da equipe; RF08 para pode_cancelar)."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from tests.apoio import PRECISA_BANCO, TesteLeilao  # primeiro: define DATABASE_URL ficticia

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40


def em(segundos: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=segundos)).isoformat()


@PRECISA_BANCO
class EdicaoTest(TesteLeilao):
    def dados(self, **extra):
        base = {"nome": "Bicicleta aro 29", "descricao": "Bicicleta revisada, pneus novos", "categoria": "Esportes e lazer",
                "preco_inicial": "250.00", "inicio": em(300), "duracao_segundos": 600, "fotos": []}
        return {**base, **extra}

    def criar_em(self, comitente, segundos: int) -> int:
        r = comitente.post("/api/leiloes", json=self.dados(nome="Original", inicio=em(segundos)))
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["id"]

    def versao(self, cliente, leilao_id: int) -> int:
        return cliente.get(f"/api/leiloes/{leilao_id}").json()["versao"]

    def editar(self, cliente, leilao_id: int, **extra):
        dados = self.dados(**extra)
        dados["versao"] = self.versao(cliente, leilao_id)
        return cliente.put(f"/api/leiloes/{leilao_id}", json=dados)

    def test_comitente_edita_sem_ninguem_na_sala(self):
        ana = self.cadastrar_e_entrar()
        leilao_id = self.novo_leilao(ana)  # comeca em 2 min
        self.entrar(ana, leilao_id)  # o proprio comitente na sala nao bloqueia
        antes = ana.get(f"/api/leiloes/{leilao_id}/sala").json()["versao"]
        r = self.editar(ana, leilao_id)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["versao"], antes + 1)
        d = self.cliente().get(f"/api/leiloes/{leilao_id}").json()
        self.assertEqual((d["item"]["nome"], d["item"]["categoria"], d["preco_inicial"], d["preco_atual"]),
                         ("Bicicleta aro 29", "Esportes e lazer", "250.00", "250.00"))
        sala = ana.get(f"/api/leiloes/{leilao_id}/sala").json()
        self.assertEqual(sala["versao"], antes + 1)  # quem esta na sala recebe o estado novo
        inicio = datetime.fromisoformat(sala["inicio"].replace("Z", "+00:00"))
        termino = datetime.fromisoformat(sala["termino_vigente"].replace("Z", "+00:00"))
        self.assertEqual((termino - inicio).total_seconds(), 600)

    def test_outro_usuario_nao_edita(self):
        ana, bia = self.cadastrar_e_entrar(), self.cadastrar_e_entrar()
        leilao_id = self.novo_leilao(ana)
        r = bia.put(f"/api/leiloes/{leilao_id}", json={**self.dados(), "versao": 0})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["codigo"], "edicao_nao_autorizada")
        self.assertEqual(self.cliente().put("/api/leiloes/999999", json={**self.dados(), "versao": 0}).status_code, 401)
        self.assertEqual(ana.put("/api/leiloes/999999", json={**self.dados(), "versao": 0}).status_code, 404)

    def test_participantes_na_sala_nao_impedem_edicao_enquanto_agendado(self):
        ana, bia = self.cadastrar_e_entrar(), self.cadastrar_e_entrar()
        perto, longe = self.criar_em(ana, 120), self.criar_em(ana, 1200)
        self.entrar(bia, perto)
        self.entrar(bia, longe)
        for leilao_id in (perto, longe):
            r = self.editar(ana, leilao_id, inicio=em(3000))
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(self.cliente().get(f"/api/leiloes/{leilao_id}").json()["item"]["nome"],
                             "Bicicleta aro 29")

    def test_conflito_de_versao_avisa_e_nao_sobrescreve(self):
        ana = self.cadastrar_e_entrar()
        leilao_id = self.novo_leilao(ana)
        versao_inicial = self.versao(ana, leilao_id)
        primeira = ana.put(f"/api/leiloes/{leilao_id}",
                           json={**self.dados(nome="Primeira alteração"), "versao": versao_inicial})
        self.assertEqual(primeira.status_code, 200, primeira.text)

        segunda = ana.put(f"/api/leiloes/{leilao_id}",
                          json={**self.dados(nome="Segunda alteração"), "versao": versao_inicial})
        self.assertEqual(segunda.status_code, 409)
        self.assertEqual(segunda.json()["codigo"], "conflito_de_versao")
        self.assertEqual(segunda.json()["detalhes"]["versao_atual"], versao_inicial + 1)
        atual = self.cliente().get(f"/api/leiloes/{leilao_id}").json()
        self.assertEqual(atual["item"]["nome"], "Primeira alteração")
        self.assertEqual(atual["versao"], versao_inicial + 1)

        # Depois de revisar (lendo a versão nova), a edição é aceita.
        r = self.editar(ana, leilao_id, nome="Segunda alteração")
        self.assertEqual(r.status_code, 200, r.text)

    def test_em_andamento_ou_cancelado_nao_edita(self):
        ana = self.cadastrar_e_entrar()
        aberto, cancelado = self.novo_leilao(ana), self.novo_leilao(ana)
        self.abrir_agora(aberto)
        self.assertEqual(ana.post(f"/api/leiloes/{cancelado}/cancelar").status_code, 200)
        for leilao_id in (aberto, cancelado):
            r = self.editar(ana, leilao_id)
            self.assertEqual(r.status_code, 409, r.text)

    def test_dados_invalidos_nao_mudam_nada(self):
        ana = self.cadastrar_e_entrar()
        leilao_id = self.novo_leilao(ana)
        r = self.editar(ana, leilao_id, preco_inicial="0.10", nome="Outro nome")
        self.assertEqual(r.status_code, 422)
        d = self.cliente().get(f"/api/leiloes/{leilao_id}").json()
        self.assertEqual((d["item"]["nome"], d["preco_inicial"]), ("Bicicleta", "100.00"))

    def test_fotos_sao_substituidas(self):
        ana = self.cadastrar_e_entrar()
        refs = [ana.post("/api/fotos", files={"arquivo": ("a.png", PNG, "image/png")}).json()["referencia"]
                for _ in range(3)]
        r = ana.post("/api/leiloes", json=self.dados(fotos=refs))
        self.assertEqual(r.status_code, 201, r.text)
        leilao_id = r.json()["id"]
        nova = ana.post("/api/fotos", files={"arquivo": ("b.png", PNG, "image/png")}).json()["referencia"]
        r = self.editar(ana, leilao_id, fotos=[refs[2], nova])
        self.assertEqual(r.status_code, 200, r.text)
        fotos = self.cliente().get(f"/api/leiloes/{leilao_id}").json()["item"]["fotos"]
        self.assertEqual(fotos, [{"url": f"/api/fotos/{refs[2]}", "ordem": 0}, {"url": f"/api/fotos/{nova}", "ordem": 1}])

    def test_meus_leiloes_lista_so_os_meus_com_permissoes(self):
        ana, bia = self.cadastrar_e_entrar(), self.cadastrar_e_entrar()
        self.assertEqual(self.cliente().get("/api/meus-leiloes").status_code, 401)
        livre, com_lance, cancelado = self.novo_leilao(ana), self.novo_leilao(ana), self.novo_leilao(ana)
        self.novo_leilao(bia)
        self.abrir_agora(com_lance)
        self.entrar(bia, com_lance)
        r = bia.post(f"/api/leiloes/{com_lance}/lances", json={"valor": "100.00", "chave": str(uuid4())})
        self.assertEqual(r.status_code, 201, r.text)
        ana.post(f"/api/leiloes/{cancelado}/cancelar")
        itens = {i["id"]: i for i in ana.get("/api/meus-leiloes").json()["itens"]}
        self.assertEqual(set(itens), {livre, com_lance, cancelado})
        self.assertEqual(list(itens), sorted(itens, reverse=True))
        self.assertEqual((itens[livre]["pode_editar"], itens[livre]["pode_cancelar"]), (True, True))
        self.assertEqual((itens[com_lance]["pode_editar"], itens[com_lance]["pode_cancelar"]), (False, False))
        self.assertEqual((itens[com_lance]["total_lances"], itens[com_lance]["participantes"]), (1, 1))
        self.assertEqual(itens[com_lance]["preco_atual"], "100.00")
        self.assertEqual((itens[cancelado]["estado"], itens[cancelado]["pode_cancelar"]), ("cancelado", False))
