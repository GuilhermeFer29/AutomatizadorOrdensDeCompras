"""SQLModel data models for the supply chain automation domain."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import Column, Text
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


# Modelo de Usuário para autenticação
class User(SQLModel, table=True):
    __tablename__ = "users"
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    is_active: bool = Field(default=True)
    full_name: Optional[str] = Field(default=None)


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


class Fornecedor(SQLModel, table=True):
    """Entity representing a supplier."""

    __tablename__ = "fornecedores"

    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str = Field(index=True, max_length=255)
    cep: Optional[str] = Field(default=None, max_length=20)
    latitude: Optional[float] = Field(default=None)
    longitude: Optional[float] = Field(default=None)
    confiabilidade: float = Field(default=0.9, ge=0.0, le=1.0)  # 0.0 a 1.0
    prazo_entrega_dias: int = Field(default=7, ge=1, le=60)  # Dias para entrega
    criado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    atualizado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)


class OfertaProduto(SQLModel, table=True):
    """Ofertas de produtos por fornecedores (simulação de mercado)."""

    __tablename__ = "ofertas_produtos"

    id: Optional[int] = Field(default=None, primary_key=True)
    produto_id: int = Field(foreign_key="produtos.id", index=True)
    fornecedor_id: int = Field(foreign_key="fornecedores.id", index=True)
    preco_ofertado: Decimal = Field(ge=Decimal("0.01"))
    estoque_disponivel: int = Field(default=100, ge=0)
    validade_oferta: Optional[datetime] = Field(default=None)  # Data de expiração da oferta
    criado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    atualizado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)

    produto: Produto = Relationship()
    fornecedor: Fornecedor = Relationship()


class OrdemDeCompra(SQLModel, table=True):
    __tablename__ = "ordens_de_compra"

    id: Optional[int] = Field(default=None, primary_key=True)
    produto_id: int = Field(foreign_key="produtos.id")
    quantidade: int
    valor: Decimal = Field(default=Decimal("0.00"))
    status: str = Field(index=True)  # pending, approved, cancelled
    origem: str  # Automática, Manual
    data_criacao: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    produto: Produto = Relationship()


class Agente(SQLModel, table=True):
    __tablename__ = "agentes"

    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str = Field(unique=True)
    descricao: str
    status: str = Field(default="inactive")  # active, inactive
    ultima_execucao: Optional[datetime] = Field(default=None)


class ChatSession(SQLModel, table=True):
    __tablename__ = "chat_sessions"

    id: Optional[int] = Field(default=None, primary_key=True)
    criado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # Poderia ter um nome, ou estar associado a um usuário


class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="chat_sessions.id")
    sender: str  # 'human', 'agent', 'system'
    content: str = Field(sa_column=Column(Text))  # TEXT para suportar respostas longas
    metadata_json: Optional[str] = Field(default=None, sa_column=Column(Text))  # TEXT para metadados grandes
    criado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    session: ChatSession = Relationship()


class ChatContext(SQLModel, table=True):
    """Armazena contexto da sessão para memória entre mensagens."""
    __tablename__ = "chat_context"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="chat_sessions.id")
    key: str  # ex: 'current_sku', 'last_intent', 'mentioned_products'
    value: str  # Valor em string (pode ser JSON serializado)
    atualizado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatAction(SQLModel, table=True):
    """Armazena ações pendentes (botões interativos) de mensagens do chat."""
    __tablename__ = "chat_actions"

    id: Optional[int] = Field(default=None, primary_key=True)
    message_id: int = Field(foreign_key="chat_messages.id")
    action_type: str  # 'approve_purchase', 'view_details', 'adjust_quantity', etc
    action_data: str  # JSON com dados da ação
    status: str = Field(default="pending")  # pending, completed, cancelled
    criado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))