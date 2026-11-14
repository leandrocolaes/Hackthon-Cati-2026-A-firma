# Contratos compartilhados — F00

**Status:** contrato aprovado para implementacao pelos cartoes F03–F12.
As rotas de produto abaixo ainda nao existem. Este commit implementa configuracao;
nao cria endpoints, schemas Pydantic de produto ou handlers de erro. Health e WS echo
existentes permanecem como verificacao do esqueleto.

## Convencoes

Prefixo `/api`. JSON em portugues, IDs inteiros, dinheiro como string decimal com
duas casas, instantes ISO-8601 com fuso (UTC nas respostas), duracao em segundos
inteiros. `inicio` sem fuso e entrada invalida (422); nao presumir fuso local.
Sessao opaca por cookie HttpOnly, nome configuravel; nunca token no JSON.
Nome/e-mail/senha e cookies seguem [autenticacao.md](autenticacao.md).
Datas, estados, participantes e transacoes seguem [dominio.md](dominio.md).

## Rotas e exemplos

Os exemplos sao ilustrativos. GET/DELETE sem corpo usam `—`; o WS recebe
atualizacoes do servidor, nao e o canal de envio de lances. `1` identifica um
leilao, e UUIDs identificam tentativas ou referencias opacas conforme indicado.

| Metodo e rota | Acesso | Entrada de exemplo | Status e saida de exemplo |
|---|---|---|---|
| POST `/api/usuarios` | Publico | `{"nome":"Ana","email":"ana@example.com","senha":"exemplo123"}` | 201 `{"id":1,"nome":"Ana","email":"ana@example.com"}` |
| POST `/api/sessao` | Publico | `{"email":"ana@example.com","senha":"exemplo123"}` | 200 `{"usuario":{"id":1,"nome":"Ana","email":"ana@example.com"}}` e Set-Cookie HttpOnly |
| DELETE `/api/sessao` | Cookie atual | — | 204, sem corpo; invalida somente a sessao atual e remove o cookie; ausencia de sessao tambem pode retornar 204 |
| GET `/api/eu` | Sessao valida | — | 200 `{"id":1,"nome":"Ana","email":"ana@example.com"}` |
| GET `/api/config-publica` | Publico | — | 200, objeto de configuracao publica exemplificado abaixo |
| POST `/api/fotos` | Sessao valida | multipart com campo `arquivo` contendo uma imagem | 201 `{"referencia":"ref-opaca-emitida-pelo-backend","url":"/api/fotos/ref-opaca-emitida-pelo-backend"}`; 422 `entrada_invalida` (campo `arquivo`) para vazio, acima do limite ou tipo fora da lista |
| GET `/api/fotos/{referencia}` | Publico | — | 200 com os bytes da imagem (`Content-Type` do tipo detectado, cache imutavel); 404 `recurso_nao_encontrado` |
| POST `/api/leiloes` | Sessao valida | `{"nome":"Livro","descricao":"Livro em bom estado","categoria":"Outros","preco_inicial":"10.00","inicio":"2026-11-14T18:00:00Z","duracao_segundos":180,"fotos":[]}` | 201 `{"id":1,"item_id":1,"estado":"agendado"}` |
| GET `/api/leiloes?pagina=1&por_pagina=20` | Publico | — | 200 `{"itens":[{"id":1,"nome":"Livro","categoria":"Outros","foto_principal":null,"preco_atual":"10.00","estado":"agendado","inicio":"2026-11-14T18:00:00Z","termino_vigente":"2026-11-14T18:03:00Z"}],"pagina":1,"por_pagina":20,"total":1}` |
| GET `/api/leiloes/1` | Publico | — | 200 `{"id":1,"item":{"id":1,"nome":"Livro","descricao":"Livro em bom estado","categoria":"Outros","fotos":[]},"comitente":{"nome":"Ana","ref":"3f9c0a1b2c4d5e6f"},"estado":"agendado","preco_inicial":"10.00","preco_atual":"10.00","inicio":"2026-11-14T18:00:00Z","termino_vigente":"2026-11-14T18:03:00Z"}` |
| POST `/api/leiloes/1/participantes` | Sessao valida | — | 200 `{"id":7,"numero":1,"apelido":"Participante 1"}`; cria ou reaproveita participacao |
| GET `/api/leiloes/1/sala` | Sessao e participacao | — | 200, snapshot da sala exemplificado abaixo |
| POST `/api/leiloes/1/lances` | Sessao e participacao | `{"valor":"10.00","chave":"b507dc81-a9b6-4ad7-8d1c-176f664bf9cb"}` | 201 `{"lance_id":4,"leilao_id":1,"valor":"10.00","versao":2}` |
| POST `/api/leiloes/1/cancelar` | Sessao do comitente | — | 200 `{"id":1,"estado":"cancelado","encerrado_em":"2026-11-14T17:59:00Z","versao":1}` |
| PUT `/api/leiloes/1` | Sessao do comitente | corpo da criacao + `"versao":1` (a lista `fotos` substitui a anterior) | 200 `{"id":1,"item_id":1,"estado":"agendado","versao":2}`; 403 edicao_nao_autorizada; 409 edicao_nao_permitida ou conflito_de_versao |
| GET `/api/meus-leiloes` | Sessao valida | — | 200 `{"itens":[{"id":1,"nome":"Livro","categoria":"Outros","foto_principal":null,"estado":"agendado","preco_inicial":"10.00","preco_atual":"10.00","inicio":"...","termino_vigente":"...","total_lances":0,"participantes":0,"pode_editar":true,"pode_cancelar":true}]}` (todos os estados, mais recentes primeiro; `participantes` nao conta o comitente) |
| GET `/api/minhas-participacoes` | Sessao valida (nao renova) | — | 200 `{"em_disputa":[...],"vencidos":[...],"nao_vencidos":[...],"cancelados_encerrados":[...]}`; item `{"id":1,"nome":"Livro","categoria":"Outros","foto_principal":null,"estado":"vendido","preco":"105.00","termino":"...","sala_acessivel":false}` (RF27; nao inclui leiloes em que o usuario e o comitente; `encerrado_sem_lances` fica em nao_vencidos) |
| GET `/api/comitentes/{ref}` | Publico | — | 200 `{"ref":"3f9c0a1b2c4d5e6f","nome":"Ana","ativos":[<cartao do catalogo>],"encerrados":{"vendidos":1,"sem_lances":0,"cancelados":2,"recentes":[{"id":3,"nome":"Livro","categoria":"Outros","foto_principal":null,"estado":"vendido","encerrado_em":"..."}]}}`; 404 recurso_nao_encontrado (RF22: nunca e-mail, ids de usuario, lances, vencedor ou valor final) |
| WS `/api/leiloes/1/ws` | Sessao e participacao | handshake com cookie, sem corpo | 101 na conexao; mensagem `{"tipo":"estado_leilao","estado":<snapshot abaixo>}` |
| GET `/api/leiloes/1/espectador` | Publico (RF25) | — | 200 snapshot publico (abaixo); 409 leilao_fora_do_estado se nao estiver em andamento; nao cria participante nem renova sessao |
| WS `/api/leiloes/1/ws?modo=espectador` | Publico (RF25) | sem cookie (ou com, se o usuario escolheu Assistir) | 101; mensagens com o snapshot publico ate o resultado; fecha com 4409 se o leilao nao estiver em andamento na entrada |

O exemplo de criacao com `fotos: []` exige ITEM_MIN_PHOTOS=0 explicitamente no
ambiente de desenvolvimento/versao minima. Com o padrao 3, deve ser recusado.
Com fotos, enviar `fotos: ["ref-opaca-1","ref-opaca-2","ref-opaca-3"]`.
O backend define dono/comitente pela sessao, calcula terminos e valida referencias,
quantidade e posse; nunca aceitar URL arbitraria como prova de upload autorizado.
F11: o requisito de nuvem foi retirado; os bytes ficam no PostgreSQL (tabela `arquivos_fotos`)
e a referencia e um token aleatorio de 32 caracteres. O tipo e detectado pelo conteudo
(nao pelo nome/Content-Type). A mesma foto pode ser usada em mais de um leilao do dono.
A lista de fotos no detalhe retorna objetos com `url` e `ordem`, sem credenciais.

Edicao (RF23, fase 2): so o comitente, so leilao agendado, antes do inicio e sem lances.
O corpo do PUT e o da criacao mais `"versao"` (a do detalhe/meus-leiloes quando o
formulario abriu); versao diferente da atual = 409 `conflito_de_versao` com
`detalhes.versao_atual`. Valida como a criacao; incrementa `versao`, entao a sala
recebe o snapshot novo (a tela recarrega o detalhe ao ver versao nova ainda agendado).
`GET /api/leiloes/{id}` e `GET /api/meus-leiloes` informam `versao`.

### Configuracao publica — exemplo de resposta

```json
{
  "item": {"nome_minimo":3,"nome_maximo":100,"descricao_minima":10,"descricao_maxima":2000,"fotos_minimas":3,"fotos_maximas":10},
  "leilao": {"preco_inicial_minimo":"1.00","antecedencia_minima_segundos":60,"antecedencia_maxima_segundos":2592000,"duracao_minima_segundos":60,"duracao_maxima_segundos":604800},
  "foto": {"maxima_bytes":5242880,"tipos_permitidos":["image/jpeg","image/png","image/webp"]},
  "categorias": ["Eletrônicos","Casa e decoração","Moda","Esportes e lazer","Colecionáveis","Livros e mídia","Outros"]
}
```

Expor somente essa selecao de limites e categorias, nunca serializar Configuracoes
inteira: DATABASE_URL e configuracao interna nao pertencem a resposta publica.

### Sala — exemplo de resposta/snapshot

```json
{
  "id":1,"versao":1,"estado":"em_andamento","server_time":"2026-11-14T18:00:30Z",
  "inicio":"2026-11-14T18:00:00Z","termino_original":"2026-11-14T18:03:00Z","termino_vigente":"2026-11-14T18:03:00Z",
  "hard_end":"2026-11-14T18:13:00Z","prorrogacao_esgotada":false,
  "preco_atual":"10.00","lance_minimo":"10.00","lider":null,
  "total_lances":0,"ultimos_lances":[],"resultado":null,
  "meu_participante_id":7,"sou_comitente":false,"pode_dar_lance":true,"motivo_impedimento":null
}
```

`hard_end` (fase 2, RF15): termino_original + 10 min, teto de qualquer prorrogacao.
`prorrogacao_esgotada`: true quando termino_vigente ja chegou ao hard_end; a sala mostra
aviso persistente de que o encerramento e definitivo naquele horario.

Aviso de lance superado (RF26): a mensagem WS de um participante pode trazer
`"aviso":"lance_superado"` junto do snapshot, quando ele era o lider no snapshot
anterior que recebeu e o novo snapshot confirmado mostra outro lider. No maximo uma vez
por usuario e leilao (`participantes.avisado_superado_em`); so via WS (quem esta na
sala naquele momento); nunca para espectador; sem e-mail ou notificacao do navegador.

Snapshot publico do espectador (RF25): os mesmos campos de prazo e preco, mais
`"espectador":true`, com lider/lances/vencedor so por apelido
(`{"apelido":"Participante 1"}`, lances `{"apelido","valor","criado_em"}`). Nao tem
`participante_id`, id de lance, `meu_participante_id`, `sou_comitente`,
`pode_dar_lance` nem `motivo_impedimento`. E igual para todos os espectadores.

`sou_comitente` (acrescentado com o frontend da sala): indica se quem pede e o comitente,
para a tela mostrar o cancelamento so a ele. O servidor continua decidindo (RF08).

Lider: `{"participante_id":7,"apelido":"Participante 1"}`.
Lance recente: `{"id":4,"participante_id":7,"apelido":"Participante 1","valor":"10.00","criado_em":"2026-11-14T18:00:40Z"}`.
Resultado vendido: `{"vencedor":{"participante_id":7,"apelido":"Participante 1"},"valor":"10.00"}`.
Sem lances/cancelado, estado final e suficiente e resultado fica null.
Apelido usa participantes.numero; frontend troca por “Voce” ao identificar o proprio
participante. Nunca enviar nome completo/e-mail na sala. Retornar dez lances mais
recentes (criado_em e id decrescentes). Tempo restante deriva de termino_vigente e
server_time; validade e decidida no servidor, com leitura efetiva apos a trava.

## Catalogo e acesso

Pagina comeca em 1; por_pagina padrao 20, maximo 100; parametros fora da faixa dao
422, sem correcao silenciosa. Listar somente em_andamento/agendado: primeiro em
andamento por termino_vigente, depois agendado por inicio; desempate por id.
RF21 (fase 2), parametros opcionais e combinaveis de `GET /api/leiloes`:

| Parametro | Valores | Regra |
|---|---|---|
| `busca` | texto (ate 100) | parte do **nome** do item; ignora maiusculas e acentos; `%` e `_` sao literais |
| `categoria` | uma das configuradas | ignora maiusculas e acentos (`Colecionaveis`); desconhecida = lista vazia |
| `estado` | `em_andamento`, `agendado` | omitido = os dois; outro valor = 422 |
| `preco_min`, `preco_max` | decimal com ate 2 casas | inclusivos, sobre `preco_atual` (= inicial em agendado); min > max = 422 |
| `ordenar` | `padrao`, `termina`, `comeca`, `preco_asc`, `preco_desc` | desempate por id |

`total` conta so o que passou nos filtros. Exemplo:
`/api/leiloes?busca=relogio&categoria=Colecionaveis&estado=em_andamento&preco_min=100&preco_max=1000&ordenar=preco_asc&pagina=1`.

Detalhe continua publico pelo link direto nos estados finais, sem historico de
lances, participantes ou vencedor. Configuracao publica serve ao formulario,
mas o servidor sempre revalida os dados recebidos.

## Erros e reenvio

Formato unico (a implementar nos cartoes das rotas, inclusive handlers FastAPI):

```json
{"codigo":"lance_abaixo_do_minimo","mensagem":"O valor esta abaixo do minimo atual.","detalhes":{"lance_minimo":"11.00"}}
```

Validacao FastAPI/Pydantic usa 422 e codigo entrada_invalida, por exemplo:
`{"codigo":"entrada_invalida","mensagem":"Confira os campos informados.","detalhes":{"campos":[{"campo":"inicio","motivo":"Informe um instante com fuso horario."}]}}`.
Selecionar campo/motivo e nao devolver input, ctx, senha, hash, token ou corpo bruto.

| Status | Codigos previstos |
|---|---|
| 401 | sessao_invalida; credenciais_invalidas (mensagem sempre “e-mail ou senha inválidos”) |
| 403 | acesso_negado; participante_ausente; cancelamento_nao_autorizado; edicao_nao_autorizada |
| 404 | recurso_nao_encontrado |
| 409 | email_ja_cadastrado; chave_reutilizada; leilao_fora_do_estado; leilao_encerrado; lance_do_comitente; lance_do_lider; lance_abaixo_do_minimo; cancelamento_nao_permitido; edicao_nao_permitida; conflito_de_versao; item_com_leilao_ativo |
| 422 | entrada_invalida (formato, tipo, faixa, instante sem fuso ou dados obrigatorios) |
| 429 | lance_muito_rapido (RF13; `detalhes.segundos_restantes`, inteiro) |
| 503 | armazenamento_indisponivel |

Na rota de lance, ausencia de participacao e recusa de negocio: retornar **409**
com participante_ausente; 403 vale para acesso a snapshot/WS sem participacao.
Demais recusas de negocio de lance tambem usam 409 e informam lance_minimo nos
detalhes quando o recurso for acessivel. 422 fica para entrada malformada.
As restricoes de criacao (incluindo fotos) seguem 422 quando dados invalidos;
conflito de item ja ativo usa 409. Erro de infraestrutura nao e recusa de negocio.

RF13 (fase 2): um participante faz no maximo uma tentativa de lance a cada
BID_MIN_INTERVAL_SECONDS (padrao 2 s) por leilao, medida pelo relogio do banco entre
tentativas decididas (aceitas ou recusadas com 409). A recusa 429 NAO e gravada como
tentativa: reenviar a mesma chave depois do intervalo e decidido normalmente. Replay de
uma tentativa ja decidida devolve a resposta original, sem passar pelo limite.

Reenvio autenticado da mesma tentativa retorna exatamente status_http e
resposta_original guardados, sem alterar dados, versao ou marcar no corpo que e
replay. Mesma chave com outro valor/leilao retorna 409 chave_reutilizada.
401/422/404 anteriores a decisao nao sao persistidos como tentativa. O fluxo
transacional aprovado e o nome da restricao estao em dominio.md.

## Versao e comunicacao worker/API

Sem Redis, fila ou LISTEN/NOTIFY nesta versao. No F12, a API consultara a cada 1 s
a versao dos leiloes com conexoes WS ativas. Ao mudar, relera snapshot confirmado
e enviara aos clientes; possivel atraso de cerca de 1 s, alem de rede/processamento.
Enviar snapshot inicial e reconciliar ao reconectar. LISTEN/NOTIFY e evolucao.

Incrementar versao na mesma transacao de abertura, lance aceito, cancelamento ou
fechamento. Lance com prorrogacao incrementa uma vez; alterar preco, lider, prazo
e contador e uma unica operacao. Recusa, replay e criacao de participante nao
incrementam versao. Dados por usuario (como meu_participante_id) sao personalizados;
nao compartilhar um snapshot personalizado entre todos os sockets.
A consulta por versao envia estado atual e pode agrupar mudancas intermediarias;
nao e um log de eventos nem um mecanismo de notificacao garantida por lance.
Expiracao/autorizacao de cada conexao continua responsabilidade do F12/F03.
