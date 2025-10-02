"""SQLModel data models for the supply chain automation domain."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import Column
from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from sqlmodel import Field, Relationship, SQLModel


class Produto(SQLModel, table=True):
    """Entity representing a product in the catalogue."""

    __tablename__ = "produtos"

    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str = Field(index=True, max_length=255)
    sku: str = Field(index=True, unique=True, max_length=64)
    categoria: Optional[str] = Field(default=None, max_length=120)
    estoque_atual: int = Field(default=0, ge=0)
    estoque_minimo: int = Field(default=0, ge=0)
    criado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    atualizado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)

    vendas: List["VendasHistoricas"] = Relationship(back_populates="produto")
    precos: List["PrecosHistoricos"] = Relationship(back_populates="produto")
    modelos_predicao: List["ModeloPredicao"] = Relationship(back_populates="produto")


class VendasHistoricas(SQLModel, table=True):
    """Historical sales record captured per product and date."""

    __tablename__ = "vendas_historicas"

    id: Optional[int] = Field(default=None, primary_key=True)
    produto_id: int = Field(foreign_key="produtos.id", index=True)
    data_venda: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    quantidade: int = Field(ge=0, nullable=False)
    receita: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    criado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)

    produto: "Produto" = Relationship(back_populates="vendas")


class PrecosHistoricos(SQLModel, table=True):
    """Historical price observation for a product."""

    __tablename__ = "precos_historicos"

    id: Optional[int] = Field(default=None, primary_key=True)
    produto_id: int = Field(foreign_key="produtos.id", index=True)
    fornecedor: Optional[str] = Field(default=None, max_length=255)
    preco: Decimal = Field(default=Decimal("0.0000"), ge=Decimal("0.0000"))
    moeda: str = Field(default="BRL", max_length=10)
    coletado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    is_synthetic: bool = Field(default=False, nullable=False)

    produto: "Produto" = Relationship(back_populates="precos")


class ModeloPredicao(SQLModel, table=True):
    """Metadata describing trained forecasting models for a product."""

    __tablename__ = "modelos_predicao"

    id: Optional[int] = Field(default=None, primary_key=True)
    produto_id: int = Field(foreign_key="produtos.id", index=True)
    modelo_tipo: str = Field(max_length=120)
    versao: str = Field(max_length=32)
    caminho_modelo: str = Field(max_length=512)
    metricas: Optional[Dict[str, float]] = Field(
        default=None,
        sa_column=Column(MySQLJSON, nullable=True),
    )
    treinado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)

    produto: "Produto" = Relationship(back_populates="modelos_predicao")


class ModeloGlobal(SQLModel, table=True):
    """Metadata describing the aggregated catalogue forecasting model."""

    __tablename__ = "modelos_globais"

    id: Optional[int] = Field(default=None, primary_key=True)
    modelo_tipo: str = Field(max_length=120)
    versao: str = Field(max_length=32)
    holdout_dias: int = Field(default=0, ge=0)
    caminho_modelo: str = Field(max_length=512)
    caminho_relatorio: str = Field(max_length=512)
    metricas: Optional[Dict[str, float]] = Field(
        default=None,
        sa_column=Column(MySQLJSON, nullable=True),
    )
    treinado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)