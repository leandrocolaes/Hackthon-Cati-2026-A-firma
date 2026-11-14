# Contrato de autenticacao — F00 parcial / F03

## Escopo desta entrega

Modelos SQLAlchemy de usuario e sessao, suas restricoes e este contrato.
Inclui agora a migracao inicial via Alembic. Nao inclui criacao automatica de tabelas, endpoints, schemas de API,
funcoes de hash, cookies, telas, seed ou regras de leilao. As restricoes declaradas
nos modelos so passam a valer no banco depois de executar `alembic upgrade head`.

Importar `app.models` registra `Usuario` e `Sessao` em `Base.metadata`.
O Alembic devera importar esse pacote antes de consultar os metadados.
Os modelos usam SQLAlchemy; as migracoes usam Alembic, incluido nas dependencias do backend.

## Usuario

Tabela `usuarios`; classe `Usuario`; nomes em portugues sem acentos.

| Campo | Definicao |
|---|---|
| id | BIGINT, chave primaria, gerado pelo banco com Identity |
| nome | VARCHAR(100), obrigatorio, repetivel, sem espacos nas pontas e nao vazio |
| email | VARCHAR(254), obrigatorio, normalizado e UNIQUE |
| senha_hash | TEXT, obrigatorio; somente hash bcrypt da senha |
| criado_em | TIMESTAMPTZ, obrigatorio, DEFAULT now() |

A inclusao de `criado_em` preserva a data real de entrada para possiveis usos
futuros, sem implementar perfil publico ou pontuacao agora.
Todo usuario pode comprar e anunciar; nao ha coluna de papel exclusivo.

### Nome e e-mail

No F03, remover espacos nas pontas do nome e recusar resultado vazio.
Normalizar o e-mail antes de gravar e antes de comparar no login: remover
espacos nas pontas e converter para minusculas. Nao remover pontos ou sufixos `+`.
Usar checagem simples de formato, sem confirmacao por e-mail.

O banco tera `UNIQUE (email)` e
`CHECK (email = lower(btrim(email)))`: a restricao UNIQUE impede contas duplicadas
e o CHECK recusa gravacoes sem normalizacao. Consultas usam `WHERE email = :email`
com parametro previamente normalizado. A migracao deve preservar ambas as garantias.
O CHECK usa a semantica PostgreSQL de `lower` e `btrim`; a validacao de formato e
normalizacao de entrada continuam sendo responsabilidade da aplicacao.
O nome tambem tem CHECK para exigir `nome = btrim(nome)` e comprimento maior que zero.

E-mail nunca aparece na sala, listagem ou perfis publicos. O modelo de persistencia
nao e um schema de resposta: respostas da API precisam selecionar os campos permitidos.

### Senha — implementar no F03

Minimo de 8 caracteres, sem regras de complexidade; maximo de 72 bytes em UTF-8,
validado antes de chamar bcrypt. Comprimento em bytes e diferente de caracteres;
caracteres acentuados podem ocupar mais de um byte. Nao truncar silenciosamente.
Nao remover espacos nem alterar os caracteres da senha.

Guardar somente hash bcrypt. Senha e hash nunca sao devolvidos pela API nem
registrados nos logs. Login incorreto sempre retorna: “e-mail ou senha inválidos”.
Nao implementar recuperacao ou troca de senha neste escopo.

## Sessao

Tabela `sessoes`; classe `Sessao`.

| Campo | Definicao |
|---|---|
| id | BIGINT, chave primaria, gerado pelo banco com Identity |
| usuario_id | BIGINT obrigatorio; FK para usuarios.id com ON DELETE RESTRICT; indexado |
| token_hash | VARCHAR(64), obrigatorio e UNIQUE; SHA-256 hexadecimal |
| criado_em | TIMESTAMPTZ, obrigatorio, DEFAULT now() |
| expira_em | TIMESTAMPTZ, obrigatorio e indexado; sem valor padrao |

Datas representam instantes com fuso; a aplicacao trabalhara em UTC.
Nao ha `ultima_atividade_em`. No F03, criar a sessao com prazo de duas horas e
renovar `expira_em` para horario do servidor + duas horas nas acoes autenticadas
consideradas atividade. Polling e heartbeat automaticos nao devem impedir a
expiracao por inatividade humana. Cada lance precisa verificar sessao valida.

### Token — implementar no F03

Gerar token com `secrets.token_urlsafe(32)`. O navegador recebe o token original
por cookie HttpOnly; o banco armazena apenas `sha256(token).hexdigest()`.
SHA-256 e deterministico, permitindo localizar a sessao pelo indice unico.
Bcrypt usa salt aleatorio e nao deve ser usado para este campo. SHA-256 e adequado
para esse token longo e aleatorio; nao deve substituir bcrypt para senhas humanas.
Nao registrar token original, hash de token ou cookie em logs/respostas de dados.
O ID interno da sessao nao e uma credencial de acesso.

### Multiplas sessoes, logout e exclusao

Permitir varias sessoes simultaneas por usuario, com tokens e prazos independentes.
Logout apaga somente a sessao atual. Consistencia de lances sera garantida pelo
cartao correspondente com transacao/trava por leilao, independentemente da sessao.
Um eventual limite de frequencia sera por usuario, nao por sessao; nao entra aqui.

Usuario com sessoes nao pode ser excluido: FK RESTRICT e relacionamento ORM sem
cascade de exclusao, com `passive_deletes="all"`, deixam a garantia para o banco,
inclusive quando as sessoes ja estiverem carregadas. Nao ha exclusao de conta agora.
Se ela existir futuramente, sera necessario definir a politica e apagar sessoes antes.

Sessoes expiradas continuam invalidas mesmo antes de serem removidas.
Planejar limpeza periodica no F03 (por exemplo no login) ou em processo futuro;
nao criar worker nem rotina de limpeza neste commit.

## Proximos passos

1. Aplicar a revisao `0001_usuarios_sessoes` via Alembic (comandos no README).
2. Validar comportamento real em PostgreSQL, inclusive unicidade e FK.
3. F03: validacoes, bcrypt, cadastro, login, cookie, autorizacao, renovacao, logout e telas.

A revisao 0002_dominio_leiloes acrescenta item, fotos, leilao, lances, tentativas
e participante, conforme docs/dominio.md. Configuracao, contratos gerais, base
do frontend e validacao em banco real do F00 continuam pendentes.

## Validacao do segundo commit

Executado: importacao dos modelos, sintaxe Python, revisao unica, geracao offline
do SQL PostgreSQL de upgrade/downgrade, comparacao do SQL de tabelas/indices
entre modelos e migracao, e geracao de uma revisao pelo template em pasta temporaria.

Pendente: aplicar em PostgreSQL vazio, repetir `upgrade head`, executar `current`
e `check`, testar restricoes com dados reais e executar via Docker Compose.
Nao havia Docker/PostgreSQL executavel no ambiente desta entrega. Nenhum banco
foi alterado; a validacao offline nao comprova aplicacao nem comportamento real
no banco. Esses cenarios devem ser executados antes de considerar a base validada.

## Compatibilidade com F01 (commit 5dfc6c7)

No host, o PostgreSQL usa `127.0.0.1:5433`; dentro do Compose, usa `db:5432`.
Alembic reutiliza `DATABASE_URL`, definida pelo Compose ou exportada no terminal.
Nao carrega `.env` por conta propria. O Dockerfile copia configuracao e migracoes
para que `docker compose run --rm backend alembic upgrade head` funcione.

Rodar `bash scripts/verificar.sh env` antes da preparacao verifica o ambiente;
o script HTTP e o healthcheck nao substituem `alembic current` / `alembic check`.
A atualizacao de schema e manual e nao usa o mecanismo de restart dos containers.
As variaveis de sessao comentadas em `.env.example` serao conectadas ao F03;
esta entrega continua sem configuracao de dominio, seed ou endpoints novos.
