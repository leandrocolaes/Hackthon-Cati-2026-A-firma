# Validação da fase 2

Roteiro da seção 5 de `documento_de_requisitos_fase_2.md`: o que cada item cobre nos
testes automáticos (`backend/tests`, PostgreSQL real via `TEST_DATABASE_URL`) e o que
ainda precisa ser conferido na tela.

```bash
cd backend
export TEST_DATABASE_URL="postgresql+psycopg://USUARIO:SENHA@127.0.0.1:5433/BANCO_TESTE"
python -m unittest discover -s tests -v
```

| # | Validação | Teste automático | Conferir na tela |
|---|---|---|---|
| 1 | Cada fronteira de faixa (99,99 / 100,00 / 499,99 / 500,00 / …) | `test_regras`: `test_incremento_em_cada_fronteira_de_faixa`, `test_minimo_usa_a_faixa_do_preco_atual_confirmado` | "Lance mínimo" da sala muda de faixa |
| 2 | Prorrogar a < 1 min; hard end = original + 10 min, com aviso | `test_regras`: `test_exemplo_do_documento_lance_aos_9_03_leva_a_10_03`, `test_hard_end_e_original_mais_10_min`; `test_lances.test_prorrogacao_versao_uma_vez_e_teto` | Legenda "prorrogar no máximo até…" e aviso fixo no leilão "Relógio de bolso" do seed |
| 3 | Filtros isolados e combinados, página e URL | `test_catalogo` (todos) | Colar `/leiloes?busca=relogio&categoria=Colecionaveis&estado=em_andamento&preco_min=100&preco_max=1000&ordenar=preco_asc&pagina=1` em outra aba |
| 4 | Perfil público sem e-mail nem dados internos | `test_perfil.test_perfil_nao_expoe_dados_privados` | Link "Anunciado por" no detalhe |
| 5 | Duas edições concorrentes; recusa após início ou lance | `test_edicao`: `test_duas_edicoes_concorrentes_so_uma_grava`, `test_conflito_de_versao_avisa_e_nao_sobrescreve`, `test_em_andamento_ou_cancelado_nao_edita`, `test_depois_do_horario_de_inicio_nao_edita_mesmo_sem_worker` | Editar em duas abas: a segunda mostra o aviso e "Carregar os dados atuais para revisar" |
| 6 | Queda de conexão: snapshot/versão sem nova participação | `test_tempo_real.test_reconectar_volta_ao_estado_atual_sem_criar_participante_nem_renovar` | DevTools → Network → Offline e voltar; recarregar a página da sala (`?sala=1`) |
| 7 | Espectador sem login, sem controles de lance/cancelamento | `test_espectador` (todos); `test_tempo_real`: `test_espectador_sem_login_recebe_atualizacoes_ate_o_resultado`, `test_espectador_logado_e_leilao_fora_de_andamento` | Aba anônima → "Assistir sem participar": sem formulário de lance nem botões do comitente |
| 8 | Perder a liderança mais de uma vez → um único aviso | `test_tempo_real.test_aviso_de_lance_superado_uma_vez_por_usuario_e_leilao` | Dois navegadores alternando lances |
| 9 | Os quatro grupos de Minhas participações | `test_participacoes.test_quatro_grupos`; `test_seed.test_dados_da_fase_2` | Entrar como `comprador1@demo.local` |
| 10 | Relistar cada estado permitido sem herdar a disputa | `test_relistagem` (todos) | "Relistar" em Meus leilões: início e duração vêm vazios |
| 11 | Dois lances em < 2 s → recusa com tempo restante | `test_limite_lances` (todos); `test_regras.test_espera_entre_lances_arredonda_para_cima` | Botão mostra "Aguarde N s" |
