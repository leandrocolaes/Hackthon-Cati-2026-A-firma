# Decisoes do dominio de leiloes — F00

Status: decisoes aprovadas e implementadas nos modelos e na revisao
0002_dominio_leiloes. As regras operacionais dos servicos continuam planejadas,
nao implementadas. Aplicacao e validacao em PostgreSQL real estao pendentes.
A estrutura existente de Usuario, Sessao e a revisao 0001 permanecem preservadas.

## Convencoes mantidas

Nomes em portugues sem acentos; IDs BIGINT gerados pelo banco; valores monetarios
NUMERIC(12,2) / Decimal, transmitidos como strings; instantes TIMESTAMPTZ, com
tratamento UTC na aplicacao. Modelos separados em app/models/, importados pelo
__init__.py. Sem novos endpoints, telas, upload, worker, fila ou regras de lance
neste commit. Usuario e Sessao mantem o contrato de docs/autenticacao.md.

## 1. Dono e comitente

Item.usuario_id identifica o dono. Leilao.comitente_id identifica quem anunciou
naquela venda e permite verificar a proibicao de lance do comitente diretamente
na linha do leilao travada. A criacao deve garantir comitente_id = item.usuario_id.
Essa igualdade entre tabelas e responsabilidade da operacao de criacao; nao e
um CHECK simples entre colunas da mesma linha.

## 2. Item, limites e datas de criacao

Item: id, usuario_id, nome, descricao, categoria e criado_em.
Nome VARCHAR(100), descricao VARCHAR(2000); categoria como texto, validada pela
lista da configuracao. Os maximos configurados nao podem ultrapassar a capacidade
das colunas. Se a equipe aumentar essa capacidade no futuro, precisara de migracao.

Item, FotoItem, Leilao, Lance, TentativaLance e Participante terao criado_em
obrigatorio com DEFAULT now(). Usuario e Sessao ja possuem criado_em.

## 3. Dados do anuncio sem copia

O leilao consulta os dados do item, sem snapshot/copia nesta versao. O Nucleo
nao oferece edicao de item. Antes de RF23/RF28 permitir editar dados de um item
relistado, rever snapshots/versionamento para preservar o anuncio historico.
Nao implementar edicao nem relistagem agora.

## 4. Fotos

FotoItem: id, item_id, url, chave_armazenamento opcional, ordem e criado_em.
Armazenar somente referencias ao servico de nuvem, nunca arquivo/binario.
A foto principal e a primeira na ordenacao. Aplicar UNIQUE(item_id, ordem) e
CHECK(ordem >= 0). A criacao valida minimo de tres fotos; nao criar CHECK de
contagem entre linhas. O adaptador do provedor determinara como usar a chave opcional.

## 5. Estados

Leilao.estado e texto limitado por CHECK aos valores:
agendado, em_andamento, vendido, encerrado_sem_lances, cancelado.
As transicoes sao responsabilidade dos servicos futuros; um CHECK de valores
nao impede sozinho uma transicao indevida.

## 6. Precos e lider

preco_atual comeca igual a preco_inicial; lider_id comeca nulo.
A existencia de lance aceito e identificada por lider_id, nunca pela comparacao
entre precos: o primeiro lance pode igualar o preco inicial.
Aplicar CHECK(preco_atual >= preco_inicial).
Atualizar preco e lider na mesma transacao ao aceitar lance.

## 7. Resultado

Guardar lance_vencedor_id opcional e encerrado_em opcional.
O autor e o valor do lance vencedor determinam vencedor e preco final.
Preencher encerrado_em em todos os estados finais, inclusive cancelado.

Restricoes aprovadas:

- CHECK ((estado = 'vendido') = (lance_vencedor_id IS NOT NULL)).
- CHECK ((estado IN ('vendido','encerrado_sem_lances','cancelado')) = (encerrado_em IS NOT NULL)).

O fechamento precisa assegurar que o lance vencedor pertence ao proprio leilao
e e o maior lance aceito. Uma FK simples por id nao verifica todas essas regras.
A referencia Leilao -> Lance vencedor e Lance -> Leilao forma um ciclo: a migracao
deve criar as tabelas e depois adicionar a FK do vencedor, com nome explicito.
Na reversao, remover primeiro essa FK. Isso nao exige FK diferida: um leilao
novo nao tem vencedor, que so e preenchido depois de existir lance aceito.

## 8. Um leilao ativo por item

Indice unico parcial em item_id quando estado IN ('agendado','em_andamento').
Permitir varios leiloes historicos, mas no maximo um ativo por item.
O usuario fundamentou a decisao em RF28; o texto integral da banca para esse
requisito nao foi verificado nesta etapa. A restricao e uma decisao aprovada,
independentemente dessa verificacao documental pendente.

## 9. Lance aceito

Lance: id, leilao_id, usuario_id, valor e criado_em.
Aplicar CHECK(valor > 0). TentativaLance.lance_id tem UNIQUE: um lance so pode
estar associado a uma tentativa. Os demais campos obrigatorios, FKs e indexes
seguem o padrao do dominio. Recusas nao criam Lance.

## 10. Tentativa e reenvio

TentativaLance: id, usuario_id, leilao_id, chave UUID, valor_solicitado,
criado_em, lance_id opcional, situacao, status_http e resposta_original JSONB.
Situacao limitada a aceita ou recusada. Nao criar estado pendente nem coluna
processado_em. UNIQUE(usuario_id, chave) e UNIQUE(lance_id).
Resposta original e status sao obrigatorios para tentativas persistidas.
Nao armazenar credenciais no JSONB.

Mesma chave e mesmo valor/leilao recuperam o resultado original.
Mesma chave com outro valor ou leilao resulta em 409, sem substituir o original.
401 por ausencia de sessao ocorre antes de criar tentativa; nao e persistido.
A aplicacao continua exigindo sessao valida para consultar resultado protegido.

### Fluxo transacional aprovado para o F08

Decisao confirmada: inserir a tentativa somente quando estiver completa, na
mesma transacao do eventual lance e da atualizacao do leilao. Sem estado pendente,
sem linha incompleta e sem mudanca na estrutura de campos aprovada.

```text
Validar sessao, formato dos dados e existencia do leilao.
BEGIN
  SELECT leilao ... FOR UPDATE
  SELECT tentativa WHERE usuario_id = ? AND chave = ?
    Se existir: ROLLBACK e devolver resultado original;
                se valor/leilao diferirem, devolver 409.
  Ler clock_timestamp() do PostgreSQL depois de obter a trava.
  Revalidar autorizacao/sessao e verificar regras RF10 no processamento.
  Se aceito: INSERT lance e UPDATE leilao
             (preco, lider, termino, versao e prorrogacoes quando aplicavel).
  INSERT tentativa completa (situacao, status_http, resposta_original, lance_id).
COMMIT
  Se violar uq_tentativas_lance_usuario_chave:
    ROLLBACK de toda a transacao;
    em nova transacao, ler a tentativa original;
    devolver resposta original ou 409 se valor/leilao diferirem.
```

A checagem oficial da tentativa ocorre depois da trava. Uma consulta antecipada
pode otimizar replay, mas nao substitui a checagem sob a trava nem a autorizacao.
Dois reenvios no mesmo leilao sao serializados pela trava. Usar isolamento
READ COMMITTED (padrao PostgreSQL) para que a consulta depois da espera enxergue
o commit anterior; se o isolamento mudar, rever visibilidade e politica de retry.

A mesma chave em leiloes diferentes pode passar por travas diferentes. A garantia
final e UNIQUE(usuario_id, chave), com nome explicito
`uq_tentativas_lance_usuario_chave`. Tratar somente violacao dessa restricao
(SQLSTATE 23505 e constraint_name correspondente), nunca qualquer IntegrityError.
O rollback desfaz tambem lance, lider, preco, termino, contador e versao, evitando
lance sem tentativa. So publicar atualizacoes depois do commit bem-sucedido.

Recusas anteriores a decisao transacional nao criam tentativa: sessao invalida
(401), dados mal formatados (422) e leilao inexistente (404). Cada reenvio revalida
essas condicoes; a resposta pode mudar se houver novo login ou mudanca de contexto,
pois nao existe resultado persistido para recuperar nesses casos.
Recusas de negocio decididas sob a trava sao persistidas com resposta original.
Se a sessao expirar durante a espera, continuar recusando com 401 sem persistir
uma tentativa autenticada. Replay tambem exige sessao valida.

A leitura de tempo usa `clock_timestamp()`, nao `now()`: em PostgreSQL, `now()`
e fixo no inicio da transacao e pode ficar anterior ao prazo durante a espera.
`criado_em DEFAULT now()` continua adequado como data de criacao; nao e o relogio
usado para decidir validade temporal. A implementacao deste fluxo pertence ao F08.

## 11. Participante sem presenca temporaria

Criar somente Participante, sem PresencaSala.
Campos: id, leilao_id, usuario_id, numero e criado_em.
UNIQUE(leilao_id, usuario_id) e UNIQUE(leilao_id, numero).
O numero define apelido estavel dentro do leilao; o proprio usuario aparece como
Voce. A atribuicao concorrente de numeros sera resolvida ao implementar a entrada.

Decisao de produto: estar na sala significa ter registro de Participante no leilao.
Esse registro nao expira ao fechar aba, desconectar ou sair da sessao.
Lance continua exigindo sessao valida e as demais regras de elegibilidade.
Apelido pertence ao usuario/leilao, nao ao aparelho ou sessao.
Presenca por aba com expiracao fica para revisao futura na sala WebSocket e RF25.
Essa interpretacao substitui a proposta anterior de presenca expiravel do guia.

## 12. Agenda, versao e prorrogacoes

Leilao: id, item_id, comitente_id, preco_inicial, preco_atual, inicio,
termino_original, termino_vigente, estado, lider_id, lance_vencedor_id,
encerrado_em, criado_em, versao e prorrogacoes.
Versao comeca em 0; prorrogacoes e INT com DEFAULT 0.
Nao guardar duracao separada, pois deriva de inicio e termino_original.
Aplicar CHECK(termino_vigente >= termino_original) e
CHECK(termino_original > inicio).
O teto de prorrogacao e regra de codigo/configuracao, nao numero fixo em CHECK.
Guardar contador agora nao implementa incremento variavel nem outras evolucoes.

O DEFAULT now() representa o inicio da transacao PostgreSQL. Nao usar criado_em
como autoridade para validar prazo depois de esperar uma trava. O futuro fluxo
de lance deve ler tempo efetivo apos obter a trava; se precisar registrar o
instante efetivo do aceite em criado_em, devera atribui-lo explicitamente.

## 13. Exclusao e historico

FKs com ON DELETE RESTRICT e relacionamentos sem cascade automatica de exclusao.
Quando aplicavel, passive_deletes='all' evita que o ORM tente desvincular filhos
em vez de deixar o banco recusar a exclusao. Aplicar tambem a fotos e participantes.
Nao implementar exclusao de conta, item, historico ou dados de demonstracao aqui.

## 14. Ordem e concorrencia

Nao implementar fila persistida. A equipe define ordem de chegada operacional
como ordem de obtencao da trava da linha do leilao. Essa e a ordem de processamento:
cada lance e avaliado contra o estado deixado pelo anterior.

Essa e uma interpretacao adotada pela equipe para RF11, nao comprovacao de FIFO
por chegada HTTP/rede. A trava serializa acesso, mas nao promete essa ordem externa.
Registrar a decisao no README e demonstrar a consistencia com testes no F08/F13.
Se a banca exigir criterio de prioridade diferente, rever essa interpretacao.

## 15. Execucao, revisao e validacao

Implementar os modelos, registrar todos em models/__init__.py e criar revisao
posterior a 0001_usuarios_sessoes; nao reescrever a migracao existente.
Preservar usuarios/sessoes ja gravados. Criar indices para as consultas previstas,
incluindo agenda por estado/prazo e historico por leilao.

Validar importacao/relacionamentos, SQL, upgrade a partir de banco vazio e da
primeira revisao, repeticao do upgrade, constraints reais e alembic check.
Distinguir verificacao offline de aplicacao real; o ambiente anterior nao tinha
Docker/PostgreSQL executavel. Apresentar diff explicado antes de criar commit.
Nenhuma migracao em banco compartilhado ou VM sem confirmar destino e impacto.

## Fontes e limites

Decisoes fornecidas pelo usuario nesta conversa, aprovando/corrigindo os 15 itens
do planejamento. Requisitos e guia existentes continuam sendo referencias para
os outros cartoes. Este documento distingue a estrutura implementada das regras futuras e nao
substitui os testes da banca. Este commit adiciona somente modelos, migracao,
testes de restricoes e documentacao; nao implementa operacoes de leilao.

## Detalhes da implementacao e validacao

Entidades registradas: Usuario, Sessao, Item, FotoItem, Leilao, Lance,
TentativaLance e Participante. Nao foi criada PresencaSala.

Leilao.lance_vencedor e um relacionamento somente de leitura (viewonly).
O futuro fechamento deve atribuir lance_vencedor_id, estado e encerrado_em
juntos; atribuir apenas ao relacionamento de leitura nao persiste alteracoes.
A FK `fk_leiloes_lance_vencedor` usa use_alter para criar/remover a dependencia
circular na ordem correta. Nao ha exclusao automatica de colecoes pelo ORM.

preco_atual deve ser inicializado explicitamente pela criacao com preco_inicial;
nao ha DEFAULT que copie outra coluna. estado tem DEFAULT agendado, versao e
prorrogacoes tem DEFAULT 0. A estrutura nao implementa preenchimento automatico
de regra de negocio. A categoria usa VARCHAR sem limite fixo; URLs/chaves de foto
usam TEXT. chave usa UUID nativo e resposta_original usa JSONB obrigatorio;
None e tratado como SQL NULL, para nao contornar NOT NULL com JSON null.

Executado nesta entrega: importacao dos oito modelos, configuracao dos
relacionamentos, sintaxe Python, cadeia unica de revisoes, geracao offline do
upgrade e downgrade PostgreSQL e comparacao completa entre modelos/migracoes
(colunas, tipos, nulabilidade, defaults, Identity, PK, FK, UNIQUE, CHECK e indices).
Confirmado offline que downgrade 0002 -> 0001 preserva tabelas de autenticacao.

Seis testes de integracao foram adicionados em tests/test_dominio_db.py:
preservacao de usuarios/sessoes e alembic check; e-mail e exclusao;
ordem de fotos e apelidos; exclusividade de leilao ativo; coerencia de estado,
agenda, preco e resultado; unicidade e integridade das tentativas completas.
Eles criam schema aleatorio em banco de testes e removem somente esse schema.
Nao implementam/testam a logica transacional do F08, que ainda nao existe.

A descoberta dos seis testes foi executada, mas todos foram ignorados por falta
de TEST_DATABASE_URL. Nao houve validacao real das restricoes nem aplicacao das
migracoes em PostgreSQL. Nao havia Docker/PostgreSQL disponivel; a tentativa de
instalar PostgreSQL temporario via pgserver nao encontrou distribuicao compativel.
Essa pendencia impede declarar a base validada em banco real ou o F00 concluido.

## Configuracao e contratos compartilhados

app/config.py agora centraliza limites aprovados, carregando o .env da raiz com
prioridade do ambiente e cache por processo. Regras de criacao e sala continuam
nao implementadas. docs/contratos.md documenta rotas, exemplos e codigos de erro,
sem schemas de produto. Usar Decimal para preco minimo e limites compativeis com
VARCHAR(100)/VARCHAR(2000). Alteracao de configuracao exige reinicio/recriacao.

ITEM_MIN_PHOTOS aceita 0 na versao minima; padrao 3 e intervalo 0 <= min <= max.
O minimo de tres fotos e a nuvem continuam obrigatorios para a entrega do Nucleo.
A API consultara versoes a cada 1 s para atualizar sockets no F12; participante
novo nao altera versao, assim como recusa/replay. Abertura, lance aceito com sua
prorrogacao, cancelamento e fechamento incrementam versao atomicamente.
