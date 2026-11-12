"""Carga inicial: cria as tabelas e cadastra as classificações padrão (se o banco estiver vazio)."""
from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import Classificacao

DESPESAS_PADRAO = [
    "INSUMOS AGRÍCOLAS",
    "MANUTENÇÃO E OPERAÇÃO",
    "RECURSOS HUMANOS",
    "SERVIÇOS OPERACIONAIS",
    "INFRAESTRUTURA E UTILIDADES",
    "ADMINISTRATIVAS",
    "SEGUROS E PROTEÇÃO",
    "IMPOSTOS E TAXAS",
    "INVESTIMENTOS",
]

RECEITAS_PADRAO = [
    "VENDA DE PRODUTOS",
    "PRESTAÇÃO DE SERVIÇOS",
    "ARRENDAMENTO",
    "RECEITAS FINANCEIRAS",
]


def inicializar_banco() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        existe = db.scalar(select(Classificacao.id).limit(1))
        if existe:
            return
        for d in DESPESAS_PADRAO:
            db.add(Classificacao(tipo="DESPESA", descricao=d))
        for r in RECEITAS_PADRAO:
            db.add(Classificacao(tipo="RECEITA", descricao=r))
        db.commit()


if __name__ == "__main__":
    inicializar_banco()
    print("Banco inicializado.")
