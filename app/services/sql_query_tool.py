"""
Ferramenta SQL para consultas estruturadas ao banco de dados.
Complementa o RAG permitindo consultas com filtros, agregações e comparações.
"""

from typing import List, Dict, Any
from sqlmodel import Session, select, func, and_, or_
from app.models.models import Produto


def query_products_with_filters(
    db_session: Session,
    estoque_baixo: bool = None,
    categoria: str = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Consulta produtos com filtros estruturados.
    
    Args:
        db_session: Sessão do banco de dados
        estoque_baixo: Se True, retorna apenas produtos com estoque <= mínimo
        categoria: Filtrar por categoria específica
        limit: Número máximo de resultados
        
    Returns:
        Lista de produtos como dicionários
    """
    query = select(Produto)
    
    # Aplicar filtros
    conditions = []
    
    if estoque_baixo is True:
        conditions.append(Produto.estoque_atual <= Produto.estoque_minimo)
    
    if categoria:
        conditions.append(Produto.categoria == categoria)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    # Ordenar por estoque mais crítico primeiro
    if estoque_baixo:
        query = query.order_by((Produto.estoque_atual - Produto.estoque_minimo).asc())
    
    query = query.limit(limit)
    
    products = db_session.exec(query).all()
    
    return [
        {
            "id": p.id,
            "sku": p.sku,
            "nome": p.nome,
            "categoria": p.categoria,
            "estoque_atual": p.estoque_atual,
            "estoque_minimo": p.estoque_minimo,
            "estoque_baixo": p.estoque_atual <= p.estoque_minimo,
            "diferenca": p.estoque_atual - p.estoque_minimo
        }
        for p in products
    ]


def get_stock_statistics(db_session: Session) -> Dict[str, Any]:
    """
    Retorna estatísticas gerais sobre o estoque.
    
    Returns:
        Dicionário com estatísticas agregadas
    """
    # Total de produtos
    total_produtos = db_session.exec(select(func.count(Produto.id))).one()
    
    # Produtos com estoque baixo
    produtos_estoque_baixo = db_session.exec(
        select(func.count(Produto.id))
        .where(Produto.estoque_atual <= Produto.estoque_minimo)
    ).one()
    
    # Estoque total
    estoque_total = db_session.exec(
        select(func.sum(Produto.estoque_atual))
    ).one() or 0
    
    # Produtos por categoria
    categorias = db_session.exec(
        select(Produto.categoria, func.count(Produto.id))
        .group_by(Produto.categoria)
    ).all()
    
    return {
        "total_produtos": total_produtos,
        "produtos_estoque_baixo": produtos_estoque_baixo,
        "estoque_total_unidades": estoque_total,
        "produtos_por_categoria": {cat: count for cat, count in categorias if cat}
    }


def search_products_by_name_or_sku(
    db_session: Session,
    search_term: str,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Busca produtos por nome ou SKU (busca textual simples).
    
    Args:
        db_session: Sessão do banco de dados
        search_term: Termo de busca
        limit: Número máximo de resultados
        
    Returns:
        Lista de produtos encontrados
    """
    search_pattern = f"%{search_term}%"
    
    query = select(Produto).where(
        or_(
            Produto.nome.ilike(search_pattern),
            Produto.sku.ilike(search_pattern),
            Produto.categoria.ilike(search_pattern)
        )
    ).limit(limit)
    
    products = db_session.exec(query).all()
    
    return [
        {
            "id": p.id,
            "sku": p.sku,
            "nome": p.nome,
            "categoria": p.categoria,
            "estoque_atual": p.estoque_atual,
            "estoque_minimo": p.estoque_minimo,
            "estoque_baixo": p.estoque_atual <= p.estoque_minimo
        }
        for p in products
    ]


def get_products_sorted_by_stock(
    db_session: Session,
    order: str = "asc",
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Retorna produtos ordenados por estoque.
    
    Args:
        db_session: Sessão do banco de dados
        order: "asc" para menor estoque primeiro, "desc" para maior
        limit: Número máximo de resultados
        
    Returns:
        Lista de produtos ordenados
    """
    query = select(Produto)
    
    if order == "asc":
        query = query.order_by(Produto.estoque_atual.asc())
    else:
        query = query.order_by(Produto.estoque_atual.desc())
    
    query = query.limit(limit)
    
    products = db_session.exec(query).all()
    
    return [
        {
            "sku": p.sku,
            "nome": p.nome,
            "categoria": p.categoria,
            "estoque_atual": p.estoque_atual,
            "estoque_minimo": p.estoque_minimo,
            "estoque_baixo": p.estoque_atual <= p.estoque_minimo
        }
        for p in products
    ]
