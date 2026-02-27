import logging
from datetime import UTC

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.security import get_current_user
from app.core.tenant import get_tenant_session
from app.models.models import PrecosHistoricos, Produto
from app.services.product_service import create_product, delete_product, get_product_by_id, get_products, update_product

logger = logging.getLogger(__name__)

class ProductCreate(BaseModel):
    sku: str
    name: str
    price: float
    stock: int
    categoria: str | None = None
    estoque_minimo: int | None = None

class ProductUpdate(BaseModel):
    name: str | None = None
    price: float | None = None
    stock: int | None = None
    categoria: str | None = None
    estoque_minimo: int | None = None

router = APIRouter(prefix="/api/products", tags=["api-products"])


def sync_rag_background():
    """
    Função para sincronizar RAG em background após mudanças no banco.

    Executa a sincronização sem bloquear a resposta da API.
    """
    try:
        from app.services.rag_sync_service import trigger_rag_sync
        logger.info("🔄 Sincronizando RAG em background após mudança no banco...")
        result = trigger_rag_sync()
        if result["status"] == "success":
            logger.info(f"✅ RAG sincronizado: {result['products_indexed']} produtos")
        else:
            logger.warning(f"⚠️ Erro ao sincronizar RAG: {result['message']}")
    except Exception as e:
        logger.error(f"❌ Erro ao sincronizar RAG em background: {e}")


@router.get("/")
def read_products(search: str | None = None, session: Session = Depends(get_tenant_session), current_user=Depends(get_current_user)):
    """
    Retorna lista de produtos com preço atual e fornecedor padrão.

    Utiliza batch queries para evitar N+1.
    """
    from collections import Counter
    from datetime import datetime, timedelta

    from sqlalchemy import desc, func

    produtos = get_products(session, search)
    if not produtos:
        return []

    produto_ids = [p.id for p in produtos]

    # --- Batch: preço mais recente por produto (subquery) ---
    latest_ts_sub = (
        select(PrecosHistoricos.produto_id, func.max(PrecosHistoricos.coletado_em).label("max_ts"))
        .where(PrecosHistoricos.produto_id.in_(produto_ids))
        .group_by(PrecosHistoricos.produto_id)
        .subquery()
    )
    latest_prices_rows = session.exec(
        select(PrecosHistoricos)
        .join(
            latest_ts_sub,
            (PrecosHistoricos.produto_id == latest_ts_sub.c.produto_id)
            & (PrecosHistoricos.coletado_em == latest_ts_sub.c.max_ts),
        )
    ).all()
    latest_price_map: dict[int, float] = {
        p.produto_id: float(p.preco) for p in latest_prices_rows
    }

    # --- Batch: preços dos últimos 30 dias ---
    data_limite = datetime.now(UTC) - timedelta(days=30)
    recent_prices = list(session.exec(
        select(PrecosHistoricos)
        .where(PrecosHistoricos.produto_id.in_(produto_ids))
        .where(PrecosHistoricos.coletado_em >= data_limite)
    ))

    # Agrupar por produto_id
    prices_by_product: dict[int, list] = {}
    for p in recent_prices:
        prices_by_product.setdefault(p.produto_id, []).append(p)

    result = []
    for produto in produtos:
        preco_atual = latest_price_map.get(produto.id, 0.0)
        precos_recentes = prices_by_product.get(produto.id, [])

        if precos_recentes:
            preco_medio = sum(float(p.preco) for p in precos_recentes) / len(precos_recentes)
            fornecedores = [p.fornecedor for p in precos_recentes if p.fornecedor]
            if fornecedores:
                fornecedor_counter = Counter(fornecedores)
                fornecedor_padrao = fornecedor_counter.most_common(1)[0][0]
            else:
                fornecedor_padrao = None
        else:
            preco_medio = preco_atual
            fornecedor_padrao = None

        result.append({
            "id": produto.id,
            "sku": produto.sku,
            "nome": produto.nome,
            "categoria": produto.categoria,
            "preco_atual": preco_atual,
            "preco_medio": preco_medio,
            "fornecedor_padrao": fornecedor_padrao,
            "estoque_atual": produto.estoque_atual,
            "estoque_minimo": produto.estoque_minimo,
            "criado_em": produto.criado_em.isoformat(),
            "atualizado_em": produto.atualizado_em.isoformat(),
        })

    return result


@router.get("/{product_id}")
def read_product(product_id: int, session: Session = Depends(get_tenant_session), current_user=Depends(get_current_user)):
    product = get_product_by_id(session, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("/")
def handle_create_product(
    product: ProductCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_tenant_session),
    current_user=Depends(get_current_user),
):
    """
    Cria um novo produto e sincroniza RAG automaticamente.

    A sincronização do RAG acontece em background para não atrasar a resposta.
    """
    created_product = create_product(session, product.model_dump())

    # Sincroniza RAG em background
    background_tasks.add_task(sync_rag_background)
    logger.info(f"📦 Produto criado: {product.sku} - RAG será sincronizado")

    return created_product


@router.put("/{product_id}")
def handle_update_product(
    product_id: int,
    product: ProductUpdate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_tenant_session),
    current_user=Depends(get_current_user),
):
    """
    Atualiza um produto e sincroniza RAG automaticamente.

    A sincronização do RAG acontece em background para não atrasar a resposta.
    """
    updated_product = update_product(session, product_id, product.model_dump(exclude_unset=True))
    if not updated_product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Sincroniza RAG em background
    background_tasks.add_task(sync_rag_background)
    logger.info(f"🔄 Produto atualizado: ID {product_id} - RAG será sincronizado")

    return updated_product


@router.delete("/{product_id}", status_code=204)
def handle_delete_product(
    product_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_tenant_session),
    current_user=Depends(get_current_user),
):
    """
    Remove um produto e sincroniza RAG automaticamente.
    """
    deleted = delete_product(session, product_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Product not found")

    background_tasks.add_task(sync_rag_background)
    logger.info(f"🗑️ Produto removido: ID {product_id} - RAG será sincronizado")

    return None


@router.get("/{sku}/price-history")
def get_product_price_history(
    sku: str,
    limit: int = Query(default=30, ge=1, le=365),
    session: Session = Depends(get_tenant_session),
    current_user=Depends(get_current_user),
):
    """
    Retorna o histórico de preços de um produto por SKU.

    Args:
        sku: SKU do produto
        limit: Número máximo de registros (padrão: 30, máximo: 365)
    """
    # Buscar produto pelo SKU
    produto = session.exec(select(Produto).where(Produto.sku == sku)).first()
    if not produto:
        raise HTTPException(status_code=404, detail=f"Produto com SKU '{sku}' não encontrado")

    # Buscar histórico de preços
    precos = list(
        session.exec(
            select(PrecosHistoricos)
            .where(PrecosHistoricos.produto_id == produto.id)
            .order_by(PrecosHistoricos.coletado_em.desc())
            .limit(limit)
        )
    )

    # Reverter ordem para cronológica
    precos.reverse()

    return [
        {
            "date": preco.coletado_em.isoformat(),
            "coletado_em": preco.coletado_em.isoformat(),
            "preco": float(preco.preco),
            "price": float(preco.preco),
        }
        for preco in precos
    ]
