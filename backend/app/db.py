"""Conexão com o PostgreSQL via SQLAlchemy.

- engine: o "cano" até o banco (gerencia um pool de conexões).
- SessionLocal: fábrica de sessões; uma sessão = uma conversa/transação com o banco.
- Base: classe-mãe dos futuros models (tabelas).
- get_db: entrega uma sessão para cada requisição e fecha no final.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
