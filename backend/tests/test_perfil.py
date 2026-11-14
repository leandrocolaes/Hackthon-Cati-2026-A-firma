"""RF22: perfil publico do comitente, sem dados privados."""

import json
from uuid import uuid4

from tests.apoio import PRECISA_BANCO, TesteLeilao  # primeiro: define DATABASE_URL ficticia


@PRECISA_BANCO
class PerfilPublicoTest(TesteLeilao):
    def test_perfil_mostra_ativos_e_resumo_dos_encerrados(self):
        ana = self.cadastrar_e_entrar(nome="Ana Comitente")
        bia = self.cadastrar_e_entrar(nome="Bia")
        agendado, andamento, vendido, sem_lances, cancelado = (self.novo_leilao(ana) for _ in range(5))
        self.novo_leilao(bia)  # de outra pessoa: nao aparece
        self.abrir_agora(andamento)
        self.abrir_agora(vendido)
        self.entrar(bia, vendido)
        r = bia.post(f"/api/leiloes/{vendido}/lances", json={"valor": "100.00", "chave": str(uuid4())})
        self.assertEqual(r.status_code, 201, r.text)
        self.banco.sql("""UPDATE leiloes SET estado='vendido', encerrado_em=clock_timestamp(),
                          lance_vencedor_id=(SELECT id FROM lances WHERE leilao_id=:id) WHERE id=:id""", id=vendido)
        self.banco.sql("UPDATE leiloes SET estado='encerrado_sem_lances', encerrado_em=clock_timestamp() "
                       "WHERE id=:id", id=sem_lances)
        self.assertEqual(ana.post(f"/api/leiloes/{cancelado}/cancelar").status_code, 200)

        ref = self.cliente().get(f"/api/leiloes/{agendado}").json()["comitente"]["ref"]
        r = self.cliente().get(f"/api/comitentes/{ref}")  # publico: sem login
        self.assertEqual(r.status_code, 200, r.text)
        p = r.json()
        self.assertEqual(set(p), {"ref", "nome", "ativos", "encerrados"})
        self.assertEqual(p["nome"], "Ana Comitente")
        self.assertEqual([a["id"] for a in p["ativos"]], [andamento, agendado])  # ordem do catalogo
        e = p["encerrados"]
        self.assertEqual((e["vendidos"], e["sem_lances"], e["cancelados"]), (1, 1, 1))
        self.assertEqual({x["id"] for x in e["recentes"]}, {vendido, sem_lances, cancelado})
        self.assertEqual(set(e["recentes"][0]), {"id", "nome", "categoria", "foto_principal", "estado",
                                                 "encerrado_em"})

    def test_perfil_nao_expoe_dados_privados(self):
        ana = self.cadastrar_e_entrar(nome="Ana")
        leilao = self.novo_leilao(ana)
        detalhe = self.cliente().get(f"/api/leiloes/{leilao}").json()
        self.assertEqual(set(detalhe["comitente"]), {"nome", "ref"})
        ref = detalhe["comitente"]["ref"]
        self.assertNotEqual(ref, str(ana.usuario_id))
        texto = self.cliente().get(f"/api/comitentes/{ref}").text + json.dumps(detalhe)
        self.assertNotIn(ana.email, texto)
        self.assertNotIn("usuario_id", texto)
        self.assertNotIn("comitente_id", texto)
        self.assertNotIn("senha", texto)
        self.assertNotIn("sess", texto)

    def test_ref_inexistente_e_404_e_refs_sao_unicas(self):
        self.assertEqual(self.cliente().get("/api/comitentes/naoexiste").status_code, 404)
        refs = {self.banco.sql("SELECT ref_publica FROM usuarios WHERE id=:id",
                               id=self.cadastrar_e_entrar().usuario_id).scalar_one() for _ in range(3)}
        self.assertEqual(len(refs), 3)
        self.assertTrue(all(len(r) == 16 for r in refs))
