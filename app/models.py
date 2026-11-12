"""Entidades do sistema.

PESSOAS          -> Fornecedor, Cliente e Faturado (campo tipo)
CLASSIFICACAO    -> Tipo de Receita e Tipo de Despesa (campo tipo)
MOVIMENTOCONTAS  -> Contas a Pagar (APAGAR) e Contas a Receber (ARECEBER)
PARCELACONTAS    -> Parcelas de um movimento (uma ou mais, com vencimentos distintos)
MOVIMENTO_CLASSIFICACAO -> um movimento pode ter uma ou mais classificações
"""
from datetime import date, datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

STATUS_ATIVO = "ATIVO"
STATUS_INATIVO = "INATIVO"

movimento_classificacao = Table(
    "movimento_classificacao",
    Base.metadata,
    Column("movimento_id", ForeignKey("movimentocontas.id"), primary_key=True),
    Column("classificacao_id", ForeignKey("classificacao.id"), primary_key=True),
)


class Pessoa(Base):
    __tablename__ = "pessoas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tipo: Mapped[str] = mapped_column(String(20), index=True)  # FORNECEDOR | CLIENTE | FATURADO
    razao_social: Mapped[str] = mapped_column(String(200))
    fantasia: Mapped[str | None] = mapped_column(String(200), nullable=True)
    documento: Mapped[str | None] = mapped_column(String(20), index=True, nullable=True)  # CPF/CNPJ só dígitos
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(10), default=STATUS_ATIVO, index=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Classificacao(Base):
    __tablename__ = "classificacao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tipo: Mapped[str] = mapped_column(String(10), index=True)  # RECEITA | DESPESA
    descricao: Mapped[str] = mapped_column(String(150))
    status: Mapped[str] = mapped_column(String(10), default=STATUS_ATIVO, index=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class MovimentoContas(Base):
    __tablename__ = "movimentocontas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tipo: Mapped[str] = mapped_column(String(10), index=True)  # APAGAR | ARECEBER
    numero_nota_fiscal: Mapped[str | None] = mapped_column(String(50), nullable=True)
    data_emissao: Mapped[date | None] = mapped_column(Date, nullable=True)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    valor_total: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    pessoa_id: Mapped[int] = mapped_column(ForeignKey("pessoas.id"))  # fornecedor (APAGAR) ou cliente (ARECEBER)
    faturado_id: Mapped[int | None] = mapped_column(ForeignKey("pessoas.id"), nullable=True)
    origem: Mapped[str] = mapped_column(String(20), default="MANUAL")  # MANUAL | NOTA_FISCAL
    status: Mapped[str] = mapped_column(String(10), default=STATUS_ATIVO, index=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    pessoa: Mapped[Pessoa] = relationship(foreign_keys=[pessoa_id])
    faturado: Mapped[Pessoa | None] = relationship(foreign_keys=[faturado_id])
    classificacoes: Mapped[list[Classificacao]] = relationship(secondary=movimento_classificacao)
    parcelas: Mapped[list["ParcelaContas"]] = relationship(
        back_populates="movimento", cascade="all, delete-orphan", order_by="ParcelaContas.data_vencimento"
    )


class ParcelaContas(Base):
    __tablename__ = "parcelacontas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    movimento_id: Mapped[int] = mapped_column(ForeignKey("movimentocontas.id"), index=True)
    identificacao: Mapped[str] = mapped_column(String(20))  # ÚNICA, 1/3, 2/3 ...
    data_vencimento: Mapped[date] = mapped_column(Date)
    valor_parcela: Mapped[float] = mapped_column(Numeric(14, 2))
    situacao: Mapped[str] = mapped_column(String(10), default="ABERTA")

    movimento: Mapped[MovimentoContas] = relationship(back_populates="parcelas")
