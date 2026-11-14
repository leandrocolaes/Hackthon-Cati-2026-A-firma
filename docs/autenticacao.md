# Contrato de autenticacao — F00 parcial / F03

## Escopo desta entrega

Modelos SQLAlchemy de usuario e sessao, suas restricoes e este contrato.
Nao inclui migracoes, criacao automatica de tabelas, endpoints, schemas de API,
funcoes de hash, cookies, telas, seed ou regras de leilao. As restricoes declaradas
nos modelos so passam a valer no banco quando a migracao do segundo commit for aplicada.

Importar `app.models` registra `Usuario` e `Sessao` em `Base.metadata`.
O Alembic devera importar esse pacote antes de consultar os metadados.
Nenhuma nova dependencia de execucao e necessaria para os modelos.

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

1. Segundo commit: configurar Alembic e criar migracao das duas tabelas e restricoes.
2. Validar comportamento real em PostgreSQL, inclusive unicidade e FK.
3. F03: validacoes, bcrypt, cadastro, login, cookie, autorizacao, renovacao, logout e telas.

O restante do F00 (item, leilao, fotos, lances, presenca e contratos gerais)
continua pendente. Reutilizar estes modelos e acrescentar migracoes posteriores.
