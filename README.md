# Leilão Online — A firma

Esqueleto mínimo do projeto. **Não tem nenhuma funcionalidade ainda**: só liga as peças da stack e prova que elas conversam entre si. Os requisitos estão em [`documento_de_requisitos.md`](documento_de_requisitos.md).

## As peças e como elas se ligam

```
 Navegador
    │  http://<vm>/            (porta 80, a única aberta)
    ▼
 ┌──────────────── Nginx (container "frontend") ────────────────┐
 │  /           → arquivos do React já compilados               │
 │  /api/...    → repassa para o backend (HTTP e WebSocket)     │
 └──────────────────────────────┬───────────────────────────────┘
                                ▼
 ┌──────────── FastAPI (container "backend", porta 8000) ───────┐
 │  rotas /api/...  ·  regras de negócio  ·  WebSocket          │
 └──────────────────────────────┬───────────────────────────────┘
                                │  SQLAlchemy + psycopg
                                ▼
 ┌──────────── PostgreSQL (container "db", porta 5432) ─────────┐
 │  dados persistidos no volume "dbdata"                        │
 └──────────────────────────────────────────────────────────────┘
```

| Peça | Para que serve | Arquivos |
|---|---|---|
| **React + TypeScript** | A interface. Roda no navegador. | `frontend/src/` |
| **Vite** | Compila o React em HTML/JS e serve em modo de desenvolvimento. | `frontend/vite.config.ts` |
| **Nginx** | Porta de entrada: entrega o site e repassa `/api` para o backend. | `frontend/nginx.conf` |
| **FastAPI** | A API: recebe requisições, aplica regras, fala com o banco. | `backend/app/main.py` |
| **Uvicorn** | O servidor que executa o FastAPI. | `backend/Dockerfile` |
| **SQLAlchemy + psycopg** | Ponte Python ↔ PostgreSQL. | `backend/app/db.py` |
| **PostgreSQL** | Guarda os dados. Sobrevive a reinícios. | `compose.yaml` |
| **Docker Compose** | Sobe os três containers juntos, com um comando. | `compose.yaml` |

O que a página de teste demonstra:
- **`GET /api/health`**: React → Nginx → FastAPI → PostgreSQL (`SELECT now()`) e de volta. Se aparecer `"db": "ok"`, a cadeia inteira funciona.
- **`WS /api/ws`**: conexão em tempo real. O botão envia "olá" e o servidor responde na hora com o horário dele. É a base da sala do leilão (RF09).
- **`/api/docs`**: documentação automática de todas as rotas, gerada pelo FastAPI.

## Como rodar

### Tudo junto (igual vai rodar na VM)

```bash
cp .env.example .env          # somente se ainda nao existir; ajuste a senha antes de criar o banco
bash scripts/verificar.sh env
docker compose up -d db
docker compose build backend
docker compose run --rm backend alembic upgrade head
docker compose up --build
```

Abra http://localhost (ou `http://localhost:<HTTP_PORT>` se você configurou outra
porta no `.env`). Para parar: `Ctrl+C`; `docker compose down` remove os containers,
mas preserva o volume. Não use `docker compose down -v` para atualizar: ele apaga os dados.

A porta HTTP padrão é 80; `HTTP_PORT` permite usar outra porta do host. O PostgreSQL
fica acessível apenas no próprio computador em `127.0.0.1:5433`. Entre containers,
o endereço continua sendo `db:5432`; não troque a porta interna por 5433.

Para verificar página, health e handshake WebSocket do sistema em execução:

```bash
bash scripts/verificar.sh http http://localhost
```

Ajuste a URL se usar `HTTP_PORT`. Para comprovar o acesso externo à VM, execute a
verificação de outro computador com a URL da VM. O script não verifica migrações;
confirme também `alembic current` e `alembic check` conforme a seção abaixo.

### Desenvolvendo (com recarga automática)

Mais rápido para programar: só o banco fica no Docker; backend e frontend rodam na sua máquina e recarregam ao salvar.

```bash
# terminal 1 — banco
docker compose up db

# terminal 2 — backend (precisa de Python 3.12)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Use usuario, senha e banco correspondentes ao seu .env.
# A porta do host e 5433; db:5432 e somente para conexoes entre containers.
export DATABASE_URL="postgresql+psycopg://leilao:SUA_SENHA@127.0.0.1:5433/leilao"
alembic upgrade head
uvicorn app.main:app --reload

# terminal 3 — frontend (precisa de Node 22)
cd frontend
npm install
npm run dev
```

Abra http://localhost:5173. Em desenvolvimento, quem faz o papel do Nginx é o proxy do Vite (`vite.config.ts`).

## Como adicionar uma funcionalidade

O caminho é sempre o mesmo, de baixo para cima:

1. **Tabela** — crie um model em `backend/app/models/` herdando de `Base` (de `db.py`), importe-o no `models/__init__.py` e gere/revise/aplique uma migração Alembic (comandos abaixo).
2. **Rota** — crie a rota em `main.py` (ou em um arquivo próprio, com `APIRouter`) recebendo `db: Session = Depends(get_db)`.
3. **Tela** — no React, chame a rota com `fetch("/api/...")`.
4. Teste em `/api/docs` antes de ligar a tela.

## O que ficou de fora de propósito

Entra quando o requisito pedir, não antes:

| Ferramenta | Entra quando |
|---|---|
| Alembic (migrações) | Já configurado para as tabelas de autenticação; ver comandos abaixo |
| bcrypt | Login e sessões (RF01, RF02); sessão opaca persistida, sem JWT neste contrato |
| Pydantic Settings | Limites configuráveis (RF06) |
| React Router | A segunda página |
| Tailwind | Quando formos estilizar |
| Pytest, Vitest, Ruff, ESLint | Testes da concorrência e dos lances (RF11, RF12) |
| Processo de fundo (agendador) | Abertura e fechamento automáticos (RF17, RF18) |

## Decisões da equipe

Ver a seção 2 de [`documento_de_requisitos.md`](documento_de_requisitos.md).

### Base de autenticacao (F00 parcial)

Os modelos de usuario e sessao e as decisoes estao em
[`docs/autenticacao.md`](docs/autenticacao.md). A primeira migracao cria as tabelas de autenticacao; aplique-a pelos comandos abaixo.
Cadastro e login ainda nao estao implementados.

Permitimos varias sessoes por usuario, cada uma com expiracao independente.
As regras de lance serao garantidas por transacao no banco, de modo que varias
sessoes nao afetem a consistencia. Sair em um aparelho nao encerra os demais.

### Migrações do banco de dados

O backend inclui Alembic. Ele usa a mesma variável `DATABASE_URL` da API;
não coloque credenciais em `alembic.ini`. A API não cria nem migra tabelas
automaticamente. Uma pessoa executa a atualização antes de usar funcionalidades
que dependem das tabelas, sem apagar o volume do banco.

Na raiz, com `.env` configurado, para preparar o ambiente Docker (não copie o
arquivo de exemplo por cima de um `.env` existente):

```bash
bash scripts/verificar.sh env
docker compose up -d db
docker compose build backend
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend alembic current
docker compose run --rm backend alembic check
docker compose up -d --build
```

Em desenvolvimento local, dentro de `backend/`, com o ambiente virtual ativo,
as dependências instaladas e `DATABASE_URL` exportada conforme a seção de desenvolvimento:

```bash
alembic upgrade head
alembic current
alembic check
```

`upgrade head` aplica apenas migrações pendentes; repetir não recria as tabelas.
A revisão inicial é `0001_usuarios_sessoes`, que cria `usuarios`, `sessoes`,
suas restrições e índices. Alembic também mantém a tabela `alembic_version`.
`check` verifica se os modelos exigem novas migrações; precisa de banco atualizado.

Para futuras alterações, importe o novo modelo em `app/models/__init__.py`,
gere uma revisão e revise o conteúdo antes de aplicá-la:

```bash
alembic revision --autogenerate -m "descreve alteracao"
alembic upgrade head
```

Para inspecionar o SQL sem conectar ao banco (a URL ainda precisa estar configurada):

```bash
alembic upgrade head --sql
```

Não use `create_all`, `stamp head` ou `docker compose down -v` para substituir
migrações. O downgrade inicial apaga usuários e sessões: só deve ser executado
em banco descartável ou mediante decisão explícita com backup. Se essas tabelas
já existirem por criação manual, confira o schema antes de tentar a migração;
não marque uma versão como aplicada sem verificar que corresponde ao banco.

### Compatibilidade com a configuração de ambiente (F01)

O Compose injeta o `.env` no backend e define `DATABASE_URL` explicitamente com
`db:5432`. Esse endereço é usado tanto pela API quanto por Alembic dentro do
container. Fora do Docker, exporte `DATABASE_URL` com `127.0.0.1:5433`;
o Alembic não carrega o `.env` automaticamente.

Use uma senha com os caracteres permitidos em `.env.example`, pois o Compose
monta a URL de conexão diretamente. A senha do PostgreSQL é definida quando o
volume é criado: mudar só o `.env` depois não altera a senha já gravada no banco.
Se os valores divergirem, restaure a configuração correspondente ou faça uma
alteração controlada da senha no banco; não apague o volume para corrigir isso.

As variáveis opcionais de domínio em `.env.example` antecipam funcionalidades
futuras. Neste estágio não há `app/config.py`, `app/seed.py`, cadastro ou login;
comentar/descomentar essas opções não implementa essas funcionalidades.

O healthcheck da API confirma a conexão ao banco, não a existência das tabelas.
Um backend `healthy` ainda pode ter migrações pendentes. As políticas de reinício
e o script de verificação do F01 continuam independentes da execução do Alembic.

### Base do domínio de leilões (F00 parcial)

O desenho aprovado das entidades e restrições está em
[`docs/dominio.md`](docs/dominio.md). Os modelos e a revisão `0002_dominio_leiloes`
foram adicionados; endpoints, telas e regras operacionais ainda não estão implementados.

Para o Núcleo, “estar na sala” significa possuir registro de participante no leilão;
o registro é estável por usuário/leilão e não expira ao fechar uma aba. Cada lance
continua exigindo sessão válida. Presença temporária por aba fica para evolução futura.

Não haverá fila persistida de lances. A equipe define a ordem de chegada operacional
como a ordem em que o servidor obtém a trava do leilão; cada lance é processado
contra o estado confirmado anterior. Essa interpretação não promete ordem FIFO
pela chegada HTTP/rede e será validada por testes de consistência.

A revisão `0002_dominio_leiloes` acrescenta `itens`, `fotos_itens`, `leiloes`,
`lances`, `tentativas_lance` e `participantes`, preservando usuários e sessões.
Use os mesmos comandos `alembic upgrade head` para atualizar. O downgrade dessa
revisão remove os dados do domínio e não deve ser usado em banco compartilhado.

### Testes das restrições no PostgreSQL

Dentro de `backend/`, com as dependências instaladas, defina explicitamente um
banco de **testes**. Os testes criam um schema aleatório e o removem no final;
o usuário da conexão precisa de permissão para criar schemas.

```bash
export TEST_DATABASE_URL="postgresql+psycopg://USUARIO:SENHA@127.0.0.1:5433/BANCO_TESTE"
python -m unittest discover -s tests -v
```

A suíte aplica 0001, insere usuário/sessão, aplica 0002 duas vezes e verifica
preservação, correspondência com os modelos e restrições. Não usa o schema público
para as tabelas de teste. Sem `TEST_DATABASE_URL`, os seis testes são ignorados;
isso não significa que as restrições passaram. A execução real continua pendente
nesta entrega, que foi validada apenas offline. Estes testes não validam regras de
lance, concorrência ou recuperação do sistema, pertencentes aos próximos cartões.
