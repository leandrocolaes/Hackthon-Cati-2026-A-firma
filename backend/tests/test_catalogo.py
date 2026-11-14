"""RF21: busca, filtros, ordenacao e paginacao do catalogo publico."""

from datetime import datetime, timedelta, timezone

from tests.apoio import PRECISA_BANCO, TesteLeilao  # primeiro: define DATABASE_URL ficticia


def em(segundos: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=segundos)).isoformat()


@PRECISA_BANCO
class CatalogoTest(TesteLeilao):
    """Um schema so desta classe: o catalogo contem exatamente os leiloes abaixo."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ids = None

    def setUp(self):
        if CatalogoTest.ids is not None:
            return
        ana = self.cadastrar_e_entrar(nome="Ana")
        ids = {}
        for chave, nome, categoria, preco, inicio in (
            ("antigo", "Relógio antigo", "Colecionáveis", "150.00", 600),
            ("bolso", "Relógio de bolso", "Colecionáveis", "80.00", 300),
            ("bike", "Bicicleta 100% revisada", "Esportes e lazer", "1000.00", 600),
            ("livro", "Livro raro", "Livros e mídia", "50.00", 100),
            ("digital", "RELOGIO digital", "Eletrônicos", "500.00", 200),
            ("cancelado", "Relógio quebrado", "Colecionáveis", "90.00", 600),
        ):
            r = ana.post("/api/leiloes", json={
                "nome": nome, "descricao": "Descricao do item", "categoria": categoria,
                "preco_inicial": preco, "inicio": em(inicio), "duracao_segundos": 3600, "fotos": []})
            self.assertEqual(r.status_code, 201, r.text)
            ids[chave] = r.json()["id"]
        # Dois em andamento: o "antigo" ja recebeu lances (preco atual 300,00) e termina depois.
        self.abrir_agora(ids["antigo"], 200)
        self.abrir_agora(ids["bike"], 100)
        self.banco.sql("UPDATE leiloes SET preco_atual = 300.00 WHERE id = :id", id=ids["antigo"])
        self.assertEqual(ana.post(f"/api/leiloes/{ids['cancelado']}/cancelar").status_code, 200)
        CatalogoTest.ids = ids

    def nomes(self, consulta: str = "") -> list[str]:
        r = self.cliente().get(f"/api/leiloes?{consulta}")
        self.assertEqual(r.status_code, 200, r.text)
        inverso = {v: k for k, v in self.ids.items()}
        return [inverso[c["id"]] for c in r.json()["itens"]]

    def test_padrao_em_andamento_por_termino_depois_agendados_por_inicio(self):
        self.assertEqual(self.nomes(), ["bike", "antigo", "livro", "digital", "bolso"])

    def test_busca_parte_do_nome_sem_maiusculas_nem_acentos(self):
        self.assertEqual(sorted(self.nomes("busca=relogio")), ["antigo", "bolso", "digital"])
        self.assertEqual(sorted(self.nomes("busca=RELÓGIO%20DE")), ["bolso"])
        self.assertEqual(self.nomes("busca=Descricao"), [])  # descricao fica fora nesta fase
        self.assertEqual(self.nomes("busca=100%25"), ["bike"])  # % do usuario e literal
        self.assertEqual(self.nomes("busca=_"), [])

    def test_categoria_estado_e_preco(self):
        self.assertEqual(sorted(self.nomes("categoria=Colecionáveis")), ["antigo", "bolso"])
        self.assertEqual(sorted(self.nomes("categoria=colecionaveis")), ["antigo", "bolso"])
        self.assertEqual(self.nomes("estado=em_andamento"), ["bike", "antigo"])
        self.assertEqual(self.nomes("estado=agendado"), ["livro", "digital", "bolso"])
        # Preco atual confirmado (antigo = 300,00, nao o inicial 150,00); limites inclusivos.
        self.assertEqual(sorted(self.nomes("preco_min=300&preco_max=500")), ["antigo", "digital"])
        self.assertEqual(sorted(self.nomes("preco_max=80.00")), ["bolso", "livro"])

    def test_categoria_desconhecida_nao_encontra_nada(self):
        self.assertEqual(self.nomes("categoria=Inexistente"), [])

    def test_combinacao_do_exemplo_do_documento(self):
        consulta = ("busca=relogio&categoria=Colecionaveis&estado=em_andamento"
                    "&preco_min=100&preco_max=1000&ordenar=preco_asc&pagina=1")
        self.assertEqual(self.nomes(consulta), ["antigo"])

    def test_ordenacoes(self):
        self.assertEqual(self.nomes("ordenar=termina"), ["bike", "antigo", "livro", "digital", "bolso"])
        self.assertEqual(self.nomes("ordenar=comeca")[:2], ["antigo", "bike"])
        self.assertEqual(self.nomes("ordenar=comeca")[2:], ["livro", "digital", "bolso"])
        self.assertEqual(self.nomes("ordenar=preco_asc"), ["livro", "bolso", "antigo", "digital", "bike"])
        self.assertEqual(self.nomes("ordenar=preco_desc"), ["bike", "digital", "antigo", "bolso", "livro"])

    def test_paginacao_respeita_o_filtro(self):
        r = self.cliente().get("/api/leiloes?busca=relogio&por_pagina=2&pagina=2&ordenar=preco_asc").json()
        self.assertEqual((r["total"], r["pagina"], len(r["itens"])), (3, 2, 1))
        self.assertEqual(r["itens"][0]["id"], self.ids["digital"])
        self.assertEqual(self.cliente().get("/api/leiloes").json()["por_pagina"], 20)

    def test_entradas_invalidas_dao_422(self):
        for consulta in ("estado=vendido", "estado=cancelado", "ordenar=aleatorio",
                         "preco_min=abc", "preco_min=-1", "preco_min=10.001", "preco_min=500&preco_max=100"):
            with self.subTest(consulta=consulta):
                r = self.cliente().get(f"/api/leiloes?{consulta}")
                self.assertEqual(r.status_code, 422, r.text)
                self.assertEqual(r.json()["codigo"], "entrada_invalida")
