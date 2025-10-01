"""Utilities to import sales history data into the relational database."""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import BinaryIO, Dict, List, Optional, Set

import pandas as pd
from pandas import DataFrame
from sqlmodel import Session, select

from app.core.database import engine
from app.models.models import Produto, VendasHistoricas

LOGGER = logging.getLogger(__name__)

REQUIRED_COLUMNS = {"sku", "nome", "data_venda", "quantidade", "receita"}

def load_sales_dataframe(source: BinaryIO) -> DataFrame:
    """Load a CSV payload representing historical sales into a dataframe.

    The CSV must contain the columns defined in ``REQUIRED_COLUMNS``. Additional columns
    are preserved when present. The ``data_venda`` column is parsed as timezone-aware UTC
    datetimes to simplify downstream analytics.
    """

    source.seek(0)
    dataframe = pd.read_csv(source)

    missing_columns = REQUIRED_COLUMNS.difference(dataframe.columns)
    if missing_columns:
        raise ValueError(f"CSV ausente das colunas obrigatórias: {sorted(missing_columns)}")

    dataframe["data_venda"] = pd.to_datetime(dataframe["data_venda"], utc=True, errors="coerce")
    if dataframe["data_venda"].isna().any():
        raise ValueError("Algumas linhas possuem datas inválidas em 'data_venda'.")

    dataframe["quantidade"] = dataframe["quantidade"].fillna(0).astype(int)
    dataframe["receita"] = dataframe["receita"].fillna(0.0).astype(float)

    return dataframe


def ingest_sales_dataframe(dataframe: DataFrame, session: Optional[Session] = None) -> List[int]:
    """Persist all rows from the dataframe into the database.

    Parameters
    ----------
    dataframe:
        DataFrame contendo os dados a serem persistidos. É esperado que o schema tenha sido
        validado por :func:`load_sales_dataframe`.
    session:
        Sessão opcional reaproveitada durante processos em lote. Quando ``None`` uma nova
        sessão é criada e gerenciada internamente.

    Returns
    -------
    list[int]
        Lista ordenada dos ``produto_id`` impactados pela importação.
    """

    managed_session = False
    if session is None:
        session = Session(engine)
        managed_session = True

    touched_products: Set[int] = set()
    products_cache: Dict[str, Produto] = {}

    try:
        for record in dataframe.to_dict(orient="records"):
            sku = str(record["sku"]).strip()
            if not sku:
                LOGGER.warning("Linha ignorada por SKU vazio: %s", record)
                continue

            produto = products_cache.get(sku)
            if produto is None:
                produto = _get_or_create_product(record=record, session=session)
                products_cache[sku] = produto

            sale_datetime: datetime = pd.Timestamp(record["data_venda"]).to_pydatetime()
            quantidade: int = int(record["quantidade"])
            receita = Decimal(str(record["receita"]))

            existing_sale = session.exec(
                select(VendasHistoricas)
                .where(VendasHistoricas.produto_id == produto.id)
                .where(VendasHistoricas.data_venda == sale_datetime)
            ).first()

            if existing_sale:
                existing_sale.quantidade = quantidade
                existing_sale.receita = receita
            else:
                nova_venda = VendasHistoricas(
                    produto_id=produto.id,
                    data_venda=sale_datetime,
                    quantidade=quantidade,
                    receita=receita,
                )
                session.add(nova_venda)

            touched_products.add(produto.id)

        session.commit()
        LOGGER.info("Importação concluída com %d produtos atualizados.", len(touched_products))
    finally:
        if managed_session:
            session.close()

    return sorted(touched_products)


def _get_or_create_product(record: Dict[str, object], session: Session) -> Produto:
    """Retrieve an existing product by SKU or create a new record."""

    sku = str(record["sku"]).strip()
    statement = select(Produto).where(Produto.sku == sku)
    produto = session.exec(statement).first()

    if produto:
        _maybe_update_product(produto=produto, record=record)
        return produto

    produto = Produto(
        nome=str(record["nome"]).strip(),
        sku=sku,
        categoria=str(record.get("categoria", "") or "").strip() or None,
        estoque_atual=int(record.get("estoque_atual", 0) or 0),
        estoque_minimo=int(record.get("estoque_minimo", 0) or 0),
    )
    session.add(produto)
    session.flush()

    LOGGER.info("Produto criado para SKU '%s' com ID %s.", sku, produto.id)
    return produto


def _maybe_update_product(produto: Produto, record: Dict[str, object]) -> None:
    """Update mutable product attributes when present in the record."""

    categoria = record.get("categoria")
    if categoria:
        produto.categoria = str(categoria).strip()

    estoque_atual = record.get("estoque_atual")
    if estoque_atual is not None and str(estoque_atual).strip():
        produto.estoque_atual = int(estoque_atual)

    estoque_minimo = record.get("estoque_minimo")
    if estoque_minimo is not None and str(estoque_minimo).strip():
        produto.estoque_minimo = int(estoque_minimo)
        produto.atualizado_em = datetime.now(tz=produto.atualizado_em.tzinfo)
