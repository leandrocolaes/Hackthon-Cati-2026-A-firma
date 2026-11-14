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
cp .env.example .env          # e troque a senha
docker compose up --build
```

Abra http://localhost. Para parar: `Ctrl+C`; para apagar também os dados do banco: `docker compose down -v`.

### Desenvolvendo (com recarga automática)

Mais rápido para programar: só o banco fica no Docker; backend e frontend rodam na sua máquina e recarregam ao salvar.

```bash
# terminal 1 — banco
docker compose up db

# terminal 2 — backend (precisa de Python 3.12)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL="postgresql+psycopg://leilao:troque-esta-senha@localhost:5432/leilao"
uvicorn app.main:app --reload

# terminal 3 — frontend (precisa de Node 22)
cd frontend
npm install
npm run dev
```

Abra http://localhost:5173. Em desenvolvimento, quem faz o papel do Nginx é o proxy do Vite (`vite.config.ts`).

## Como adicionar uma funcionalidade

O caminho é sempre o mesmo, de baixo para cima:

1. **Tabela** — crie um model em `backend/app/` herdando de `Base` (de `db.py`).
2. **Rota** — crie a rota em `main.py` (ou em um arquivo próprio, com `APIRouter`) recebendo `db: Session = Depends(get_db)`.
3. **Tela** — no React, chame a rota com `fetch("/api/...")`.
4. Teste em `/api/docs` antes de ligar a tela.

## O que ficou de fora de propósito

Entra quando o requisito pedir, não antes:

| Ferramenta | Entra quando |
|---|---|
| Alembic (migrações) | Criarmos as primeiras tabelas (até lá, `Base.metadata.create_all`) |
| PyJWT + bcrypt | Login e sessões (RF01, RF02) |
| Pydantic Settings | Limites configuráveis (RF06) |
| React Router | A segunda página |
| Tailwind | Quando formos estilizar |
| Pytest, Vitest, Ruff, ESLint | Testes da concorrência e dos lances (RF11, RF12) |
| Processo de fundo (agendador) | Abertura e fechamento automáticos (RF17, RF18) |

## Decisões da equipe

Ver a seção 2 de [`documento_de_requisitos.md`](documento_de_requisitos.md).
