"""RF28: relistagem de leilao finalizado ou cancelado, sem herdar a disputa."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from tests.apoio import PRECISA_BANCO, TesteLeilao  # primeiro: define DATABASE_URL ficticia

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40


def em(segundos: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=segundos)).isoformat()


@PRECISA_BANCO
class RelistagemTest(TesteLeilao):
    def dados(self, **extra):
        base = {"nome": "Bicicleta relistada", "descricao": "Bicicleta revisada de novo", "categoria": "Outros",
                "preco_inicial": "80.00", "inicio": em(600), "duracao_segundos": 900, "fotos": []}
        return {**base, **extra}

    def disputado(self, ana, bruno, carla) -> int:
        """Leilao com lances, dois participantes, prorrogado e vendido."""
        leilao = self.novo_leilao(ana)
        for c in (bruno, carla):
            self.entrar(c, leilao)
        self.abrir_agora(leilao, 20)  # dentro da janela: o lance prorroga
        for cliente, valor in ((bruno, "100.00"), (carla, "105.00")):
            r = cliente.post(f"/api/leiloes/{leilao}/lances", json={"valor": valor, "chave": str(uuid4())})
            self.assertEqual(r.status_code, 201, r.text)
        self.banco.sql("""UPDATE leiloes SET estado='vendido', encerrado_em=clock_timestamp(),
                          lance_vencedor_id=(SELECT id FROM lances WHERE leilao_id=:id ORDER BY valor DESC LIMIT 1)
                          WHERE id=:id""", id=leilao)
        return leilao

    def test_relistar_cada_estado_permitido_sem_herdar_a_disputa(self):
        ana, bruno, carla = (self.cadastrar_e_entrar() for _ in range(3))
        vendido = self.disputado(ana, bruno, carla)
        sem_lances, cancelado = self.novo_leilao(ana), self.novo_leilao(ana)
        self.banco.sql("UPDATE leiloes SET estado='encerrado_sem_lances', encerrado_em=clock_timestamp() "
                       "WHERE id=:id", id=sem_lances)
        self.assertEqual(ana.post(f"/api/leiloes/{cancelado}/cancelar").status_code, 200)
        for origem in (vendido, sem_lances, cancelado):
            with self.subTest(origem=origem):
                r = ana.post(f"/api/leiloes/{origem}/relistar", json=self.dados())
                self.assertEqual(r.status_code, 201, r.text)
                novo = r.json()["id"]
                self.assertNotEqual(novo, origem)
                self.assertEqual(r.json()["estado"], "agendado")
                linha = self.banco.sql(
                    """SELECT l.estado, l.lider_id, l.lance_vencedor_id, l.prorrogacoes, l.preco_atual,
                              l.termino_original = l.termino_vigente,
                              extract(epoch FROM l.termino_original - l.inicio),
                              (SELECT count(*) FROM lances WHERE leilao_id = l.id),
                              (SELECT count(*) FROM participantes WHERE leilao_id = l.id),
                              l.item_id <> (SELECT item_id FROM leiloes WHERE id = :o)
                       FROM leiloes l WHERE l.id = :n""", n=novo, o=origem).one()
                # estado, lider, vencedor, prorrogacoes, preco (do formulario), termino nao prorrogado,
                # duracao (do formulario), lances, participantes, item novo
                self.assertEqual(tuple(linha), ("agendado", None, None, 0, Decimal("80.00"), True, 900, 0, 0, True))
        # O leilao antigo continua como era (anuncio historico preservado).
        antigo = self.cliente().get(f"/api/leiloes/{vendido}").json()
        self.assertEqual((antigo["item"]["nome"], antigo["estado"], antigo["preco_atual"]),
                         ("Bicicleta", "vendido", "105.00"))

    def test_nao_relista_ativo_nem_de_outro_comitente(self):
        ana, bia = self.cadastrar_e_entrar(), self.cadastrar_e_entrar()
        agendado, andamento = self.novo_leilao(ana), self.novo_leilao(ana)
        self.abrir_agora(andamento)
        for leilao_id in (agendado, andamento):
            r = ana.post(f"/api/leiloes/{leilao_id}/relistar", json=self.dados())
            self.assertEqual((r.status_code, r.json()["codigo"]), (409, "relistagem_nao_permitida"))
        cancelado = self.novo_leilao(ana)
        ana.post(f"/api/leiloes/{cancelado}/cancelar")
        r = bia.post(f"/api/leiloes/{cancelado}/relistar", json=self.dados())
        self.assertEqual((r.status_code, r.json()["codigo"]), (403, "relistagem_nao_autorizada"))
        self.assertEqual(ana.post("/api/leiloes/999999/relistar", json=self.dados()).status_code, 404)
        self.assertEqual(self.cliente().post(f"/api/leiloes/{cancelado}/relistar", json=self.dados()).status_code, 401)

    def test_valida_como_a_criacao_e_reaproveita_fotos(self):
        ana = self.cadastrar_e_entrar()
        refs = [ana.post("/api/fotos", files={"arquivo": ("a.png", PNG, "image/png")}).json()["referencia"]
                for _ in range(2)]
        r = ana.post("/api/leiloes", json=self.dados(fotos=refs))
        self.assertEqual(r.status_code, 201, r.text)
        origem = r.json()["id"]
        ana.post(f"/api/leiloes/{origem}/cancelar")
        r = ana.post(f"/api/leiloes/{origem}/relistar", json=self.dados(inicio=em(-60)))  # prazo antigo nao vale
        self.assertEqual((r.status_code, r.json()["codigo"]), (422, "entrada_invalida"))
        r = ana.post(f"/api/leiloes/{origem}/relistar", json=self.dados(fotos=refs))
        self.assertEqual(r.status_code, 201, r.text)
        fotos = self.cliente().get(f"/api/leiloes/{r.json()['id']}").json()["item"]["fotos"]
        self.assertEqual([f["url"] for f in fotos], [f"/api/fotos/{x}" for x in refs])
        meus = {i["id"]: i for i in ana.get("/api/meus-leiloes").json()["itens"]}
        self.assertEqual((meus[origem]["pode_relistar"], meus[r.json()["id"]]["pode_relistar"]), (True, False))
