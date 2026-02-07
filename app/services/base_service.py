"""
Base Service - Tenant-Aware CRUD Operations.

Este módulo fornece uma classe base genérica para serviços que
implementa automaticamente Row-Level Security (RLS) baseado em tenant.

ARQUITETURA:
============
- Todas as queries incluem WHERE tenant_id = X automaticamente
- Exceção: Superusers (tenant_id = None) veem todos os dados
- Queries são 100% async usando SQLAlchemy 2.0

REFERÊNCIAS:
- SQLAlchemy Async ORM: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- SQLModel: https://sqlmodel.tiangolo.com/
- FastAPI Dependencies: https://fastapi.tiangolo.com/tutorial/dependencies/

SEGURANÇA:
- NUNCA expõe dados de outro tenant (Row-Level Security)
- Valida tenant_id em create/update
- Lança TenantMismatchError em caso de violação

Autor: Sistema PMI | Atualizado: 2026-01-14
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import (
    Any,
    Generic,
    TypeVar,
)
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import SQLModel

from app.core.tenant_context import (
    TenantContext,
    TenantMismatchError,
)

LOGGER = logging.getLogger(__name__)


# Type variable para o modelo
ModelT = TypeVar("ModelT", bound=SQLModel)


class BaseService(Generic[ModelT]):
    """
    Serviço base genérico com suporte a Multi-Tenancy.

    Esta classe fornece operações CRUD básicas com filtro automático
    por tenant_id, garantindo Row-Level Security.

    Uso:
        class ProductService(BaseService[Produto]):
            model = Produto

        # Em um endpoint
        product_service = ProductService(session)
        products = await product_service.list_all()  # Filtra por tenant automaticamente

    Conforme docs SQLAlchemy Async:
    https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
    """

    # Subclasses DEVEM definir isso
    model: type[ModelT]

    def __init__(self, session: AsyncSession):
        """
        Inicializa o serviço com uma sessão async.

        Args:
            session: AsyncSession do SQLAlchemy
        """
        self.session = session
        self._tenant_id: UUID | None = TenantContext.get_current_tenant()
        self._is_superuser: bool = self._tenant_id is None

    # ========================================================================
    # PROPRIEDADES
    # ========================================================================

    @property
    def tenant_id(self) -> UUID | None:
        """Retorna tenant_id do contexto atual."""
        return self._tenant_id

    @property
    def is_superuser(self) -> bool:
        """Retorna True se contexto é superuser (sem tenant)."""
        return self._is_superuser

    # ========================================================================
    # MÉTODOS PRIVADOS (Filtro de Tenant)
    # ========================================================================

    def _apply_tenant_filter(self, query):
        """
        Aplica filtro de tenant à query.

        Conforme Row-Level Security pattern:
        - Se tenant_id existe: adiciona WHERE tenant_id = X
        - Se superuser: não filtra (vê tudo)

        Args:
            query: Query SQLAlchemy

        Returns:
            Query com filtro aplicado
        """
        if self._is_superuser:
            LOGGER.debug("Superuser mode: no tenant filter applied")
            return query

        # Verifica se modelo tem tenant_id
        if hasattr(self.model, 'tenant_id'):
            LOGGER.debug(f"Applying tenant filter: tenant_id={self._tenant_id}")
            return query.where(self.model.tenant_id == self._tenant_id)

        return query

    def _validate_tenant_on_write(self, data: ModelT | dict) -> None:
        """
        Valida tenant_id antes de criar/atualizar.

        Regras:
        - Se modelo tem tenant_id, deve ser igual ao contexto atual
        - Se superuser, permite qualquer tenant_id
        - Se tenant_id diferente, lança TenantMismatchError

        Args:
            data: Modelo ou dicionário a ser validado

        Raises:
            TenantMismatchError: Se tenant_id não corresponde
        """
        if self._is_superuser:
            return  # Superuser pode escrever em qualquer tenant

        # Extrai tenant_id do dado
        if isinstance(data, dict):
            data_tenant_id = data.get('tenant_id')
        else:
            data_tenant_id = getattr(data, 'tenant_id', None)

        # Se dado tem tenant_id diferente, erro
        if data_tenant_id is not None and data_tenant_id != self._tenant_id:
            raise TenantMismatchError(
                f"Tentativa de acessar dados de outro tenant. "
                f"Contexto: {self._tenant_id}, Dado: {data_tenant_id}"
            )

    def _inject_tenant_on_create(self, data: ModelT | dict) -> ModelT | dict:
        """
        Injeta tenant_id em dados de criação.

        Se o dado não tem tenant_id, adiciona do contexto atual.

        Args:
            data: Modelo ou dicionário

        Returns:
            Dado com tenant_id injetado
        """
        if self._is_superuser:
            return data  # Superuser pode criar sem tenant

        if not hasattr(self.model, 'tenant_id'):
            return data  # Modelo não suporta tenant

        if isinstance(data, dict):
            if 'tenant_id' not in data or data['tenant_id'] is None:
                data['tenant_id'] = self._tenant_id
        else:
            if getattr(data, 'tenant_id', None) is None:
                data.tenant_id = self._tenant_id

        return data

    # ========================================================================
    # CRUD OPERATIONS
    # ========================================================================

    async def get_by_id(self, id: Any, include_relations: list[str] = None) -> ModelT | None:
        """
        Busca entidade por ID (com filtro de tenant).

        Args:
            id: ID da entidade
            include_relations: Lista de relacionamentos a carregar

        Returns:
            Entidade encontrada ou None
        """
        query = select(self.model).where(self.model.id == id)
        query = self._apply_tenant_filter(query)

        # Eager loading de relacionamentos
        if include_relations:
            for rel in include_relations:
                query = query.options(selectinload(getattr(self.model, rel)))

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_field(
        self,
        field_name: str,
        value: Any,
        include_relations: list[str] = None
    ) -> ModelT | None:
        """
        Busca entidade por campo específico.

        Args:
            field_name: Nome do campo (ex: 'sku', 'email')
            value: Valor a buscar
            include_relations: Relacionamentos a carregar

        Returns:
            Primeira entidade encontrada ou None
        """
        field = getattr(self.model, field_name, None)
        if field is None:
            raise ValueError(f"Campo '{field_name}' não existe em {self.model.__name__}")

        query = select(self.model).where(field == value)
        query = self._apply_tenant_filter(query)

        if include_relations:
            for rel in include_relations:
                query = query.options(selectinload(getattr(self.model, rel)))

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_all(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: str = None,
        desc: bool = False,
        filters: dict[str, Any] = None,
        include_relations: list[str] = None
    ) -> Sequence[ModelT]:
        """
        Lista todas as entidades (com filtro de tenant).

        Args:
            skip: Offset para paginação
            limit: Limite de resultados
            order_by: Campo para ordenação
            desc: Se True, ordena descendente
            filters: Dicionário de filtros adicionais
            include_relations: Relacionamentos a carregar

        Returns:
            Lista de entidades
        """
        query = select(self.model)
        query = self._apply_tenant_filter(query)

        # Filtros adicionais
        if filters:
            for field_name, value in filters.items():
                field = getattr(self.model, field_name, None)
                if field is not None:
                    query = query.where(field == value)

        # Ordenação
        if order_by:
            order_field = getattr(self.model, order_by, None)
            if order_field:
                query = query.order_by(
                    order_field.desc() if desc else order_field.asc()
                )

        # Eager loading
        if include_relations:
            for rel in include_relations:
                query = query.options(selectinload(getattr(self.model, rel)))

        # Paginação
        query = query.offset(skip).limit(limit)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def count(self, filters: dict[str, Any] = None) -> int:
        """
        Conta entidades (com filtro de tenant).

        Args:
            filters: Filtros adicionais

        Returns:
            Número de entidades
        """
        query = select(func.count()).select_from(self.model)
        query = self._apply_tenant_filter(query)

        if filters:
            for field_name, value in filters.items():
                field = getattr(self.model, field_name, None)
                if field is not None:
                    query = query.where(field == value)

        result = await self.session.execute(query)
        return result.scalar_one()

    async def create(self, data: ModelT | dict[str, Any]) -> ModelT:
        """
        Cria nova entidade (injeta tenant_id automaticamente).

        Args:
            data: Modelo ou dicionário com dados

        Returns:
            Entidade criada

        Raises:
            TenantMismatchError: Se tenant_id não corresponde
        """
        # Valida e injeta tenant
        self._validate_tenant_on_write(data)
        data = self._inject_tenant_on_create(data)

        # Converte dict para modelo se necessário
        if isinstance(data, dict):
            entity = self.model(**data)
        else:
            entity = data

        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)

        LOGGER.info(f"Created {self.model.__name__} id={entity.id} tenant={self._tenant_id}")
        return entity

    async def create_many(self, items: list[ModelT | dict[str, Any]]) -> list[ModelT]:
        """
        Cria múltiplas entidades em batch.

        Args:
            items: Lista de modelos ou dicionários

        Returns:
            Lista de entidades criadas
        """
        entities = []
        for data in items:
            self._validate_tenant_on_write(data)
            data = self._inject_tenant_on_create(data)

            if isinstance(data, dict):
                entity = self.model(**data)
            else:
                entity = data

            entities.append(entity)

        self.session.add_all(entities)
        await self.session.flush()

        for entity in entities:
            await self.session.refresh(entity)

        LOGGER.info(f"Created {len(entities)} {self.model.__name__} entities")
        return entities

    async def update(self, id: Any, data: dict[str, Any]) -> ModelT | None:
        """
        Atualiza entidade por ID (com validação de tenant).

        Args:
            id: ID da entidade
            data: Dicionário com campos a atualizar

        Returns:
            Entidade atualizada ou None se não encontrada

        Raises:
            TenantMismatchError: Se tenant_id não corresponde
        """
        # Busca entidade existente (com filtro de tenant)
        entity = await self.get_by_id(id)
        if entity is None:
            return None

        # Valida tenant no dado de update
        self._validate_tenant_on_write(data)

        # Remove tenant_id do update (não pode ser alterado)
        data.pop('tenant_id', None)

        # Atualiza campos
        for key, value in data.items():
            if hasattr(entity, key):
                setattr(entity, key, value)

        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)

        LOGGER.info(f"Updated {self.model.__name__} id={id} tenant={self._tenant_id}")
        return entity

    async def delete(self, id: Any) -> bool:
        """
        Deleta entidade por ID (com filtro de tenant).

        Args:
            id: ID da entidade

        Returns:
            True se deletou, False se não encontrada
        """
        entity = await self.get_by_id(id)
        if entity is None:
            return False

        await self.session.delete(entity)
        await self.session.flush()

        LOGGER.info(f"Deleted {self.model.__name__} id={id} tenant={self._tenant_id}")
        return True

    async def delete_many(self, ids: list[Any]) -> int:
        """
        Deleta múltiplas entidades em batch.

        Args:
            ids: Lista de IDs

        Returns:
            Número de entidades deletadas
        """
        stmt = delete(self.model).where(self.model.id.in_(ids))
        stmt = self._apply_tenant_filter(stmt)

        result = await self.session.execute(stmt)
        await self.session.flush()

        count = result.rowcount
        LOGGER.info(f"Deleted {count} {self.model.__name__} entities")
        return count

    # ========================================================================
    # MÉTODOS DE BUSCA AVANÇADOS
    # ========================================================================

    async def search(
        self,
        search_term: str,
        search_fields: list[str],
        skip: int = 0,
        limit: int = 100
    ) -> Sequence[ModelT]:
        """
        Busca por termo em múltiplos campos (LIKE).

        Args:
            search_term: Termo de busca
            search_fields: Lista de campos a buscar
            skip: Offset
            limit: Limite

        Returns:
            Lista de entidades encontradas
        """
        query = select(self.model)
        query = self._apply_tenant_filter(query)

        # Constrói OR de LIKE em cada campo
        like_conditions = []
        for field_name in search_fields:
            field = getattr(self.model, field_name, None)
            if field is not None:
                like_conditions.append(field.ilike(f"%{search_term}%"))

        if like_conditions:
            query = query.where(or_(*like_conditions))

        query = query.offset(skip).limit(limit)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def exists(self, id: Any) -> bool:
        """
        Verifica se entidade existe (com filtro de tenant).

        Args:
            id: ID da entidade

        Returns:
            True se existe
        """
        entity = await self.get_by_id(id)
        return entity is not None


# ============================================================================
# SERVIÇOS ESPECÍFICOS (Exemplos)
# ============================================================================

# Os serviços específicos herdam de BaseService e podem adicionar
# métodos específicos do domínio. Veja app/services/product_service.py
