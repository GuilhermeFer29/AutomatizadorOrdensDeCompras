"""
Ferramentas Seguras do Agente - Tenant-Aware Implementation.

Este arquivo define as ferramentas que o agente pode chamar,
com suporte completo a Multi-Tenancy (Row-Level Security).

ARQUITETURA:
============
- Todas as ferramentas recebem tenant_id via TenantContext
- Queries são filtradas automaticamente por tenant
- Não há vazamento de dados entre tenants

REFERÊNCIAS:
- Agno Tools: https://docs.agno.com/tools/overview
- SQLAlchemy Async: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html

Autor: Sistema PMI | Atualizado: 2026-01-14
"""

from __future__ import annotations

import json
import logging
from datetime import UTC
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.core.tenant_context import TenantContext
from app.models.models import Fornecedor, OfertaProduto, OrdemDeCompra, PrecosHistoricos, Produto

LOGGER = logging.getLogger(__name__)


# ============================================================================
# HELPER: Async Context Manager para Tools
# ============================================================================

class TenantAwareSession:
    """
    Context manager que fornece sessão async com filtro de tenant.

    Uso:
        async with TenantAwareSession() as session:
            result = await session.execute(
                select(Produto).where(Produto.tenant_id == TenantContext.get_current_tenant())
            )
    """

    def __init__(self):
        self.session: AsyncSession | None = None
        self.tenant_id = TenantContext.get_current_tenant()
        self._session_gen = None

    async def __aenter__(self) -> AsyncSession:
        # Usa o generator get_async_session()
        self._session_gen = get_async_session()
        self.session = await self._session_gen.__anext__()
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session_gen:
            try:
                await self._session_gen.__anext__()
            except StopAsyncIteration:
                pass
        return False


def _get_tenant_filter(model):
    """
    Retorna condição de filtro de tenant para um modelo.

    Se modelo tem tenant_id, retorna WHERE tenant_id = X.
    Se superuser, retorna True (sem filtro).
    """
    tenant_id = TenantContext.get_current_tenant()

    if tenant_id is None:
        return True  # Superuser - sem filtro

    if hasattr(model, 'tenant_id'):
        return model.tenant_id == tenant_id

    return True  # Modelo sem tenant


# ============================================================================
# PRODUCT TOOLS (Tenant-Safe)
# ============================================================================

def get_product_info(product_sku: str) -> str:
    """
    Busca informações detalhadas de um produto no banco de dados.

    SEGURANÇA: Filtra automaticamente pelo tenant do contexto atual.
    Não expõe dados de outros tenants.

    Use esta ferramenta quando precisar saber estoque, preço, categoria
    de um produto específico identificado pelo SKU.

    Args:
        product_sku (str): O SKU do produto (ex: 'SKU_001').

    Returns:
        str: JSON com sku, nome, estoque_atual, estoque_minimo, etc.
    """
    import asyncio

    async def _query():
        tenant_id = TenantContext.get_current_tenant()

        async with TenantAwareSession() as session:
            # Query com filtro de tenant
            query = select(Produto).where(Produto.sku == product_sku)
            if tenant_id:
                query = query.where(Produto.tenant_id == tenant_id)

            result = await session.execute(query)
            produto = result.scalar_one_or_none()

            if not produto:
                return json.dumps({
                    "error": f"Produto com SKU {product_sku} não encontrado",
                    "tenant_filter": "aplicado" if tenant_id else "superuser"
                }, ensure_ascii=False)

            # Busca último preço
            preco_query = (
                select(PrecosHistoricos)
                .where(PrecosHistoricos.produto_id == produto.id)
                .order_by(PrecosHistoricos.coletado_em.desc())
                .limit(1)
            )
            preco_result = await session.execute(preco_query)
            ultimo_preco = preco_result.scalar_one_or_none()

            info = {
                "sku": produto.sku,
                "nome": produto.nome,
                "categoria": produto.categoria,
                "estoque_atual": produto.estoque_atual,
                "estoque_minimo": produto.estoque_minimo,
                "preco_atual": float(ultimo_preco.preco) if ultimo_preco else 0.0,
                "status_reposicao": "ALERTA" if produto.estoque_atual <= produto.estoque_minimo else "OK",
                "cobertura_dias": round(
                    produto.estoque_atual / max(1, produto.estoque_minimo) * 30, 1
                ) if produto.estoque_minimo > 0 else 999,
            }

            return json.dumps(info, ensure_ascii=False)

    # Executa async de forma síncrona (compatibilidade Agno)
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Se já tem event loop, usa thread pool
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _query())
                return future.result()
        else:
            return asyncio.run(_query())
    except RuntimeError:
        return asyncio.run(_query())


def list_all_products(
    category: str | None = None,
    only_low_stock: bool = False
) -> str:
    """
    Lista todos os produtos do catálogo com informações de estoque.

    SEGURANÇA: Retorna apenas produtos do tenant atual (Row-Level Security).

    Use para perguntas gerais sobre estoque quando não há SKU específico.
    Ex: "Como está meu estoque?" → Use esta ferramenta.

    Args:
        category: Filtrar por categoria (opcional)
        only_low_stock: Se True, retorna apenas produtos com estoque baixo

    Returns:
        str: JSON com lista de produtos, resumo e alertas
    """
    import asyncio

    async def _query():
        tenant_id = TenantContext.get_current_tenant()

        async with TenantAwareSession() as session:
            # Query base com filtro de tenant
            query = select(Produto)
            if tenant_id:
                query = query.where(Produto.tenant_id == tenant_id)

            # Filtros adicionais
            if category:
                query = query.where(Produto.categoria == category)

            result = await session.execute(query)
            produtos = result.scalars().all()

            # Classifica produtos
            estoque_ok = []
            estoque_alerta = []
            estoque_critico = []

            for p in produtos:
                item = {
                    "sku": p.sku,
                    "nome": p.nome,
                    "categoria": p.categoria or "Sem categoria",
                    "estoque_atual": p.estoque_atual,
                    "estoque_minimo": p.estoque_minimo,
                }

                # Classifica por status
                if p.estoque_atual <= 0:
                    item["status"] = "CRÍTICO"
                    item["urgencia"] = "IMEDIATA"
                    estoque_critico.append(item)
                elif p.estoque_atual <= p.estoque_minimo:
                    item["status"] = "ALERTA"
                    item["urgencia"] = "ALTA"
                    estoque_alerta.append(item)
                else:
                    item["status"] = "OK"
                    item["urgencia"] = None
                    if not only_low_stock:
                        estoque_ok.append(item)

            # Monta resposta
            response = {
                "total_produtos": len(produtos),
                "tenant_id": str(tenant_id) if tenant_id else "superuser",
                "resumo": {
                    "estoque_ok": len(estoque_ok),
                    "estoque_alerta": len(estoque_alerta),
                    "estoque_critico": len(estoque_critico),
                },
                "alertas_prioritarios": estoque_critico + estoque_alerta,
            }

            if not only_low_stock:
                response["produtos"] = estoque_ok + estoque_alerta + estoque_critico
            else:
                response["produtos"] = estoque_critico + estoque_alerta

            return json.dumps(response, ensure_ascii=False)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _query())
                return future.result()
        else:
            return asyncio.run(_query())
    except RuntimeError:
        return asyncio.run(_query())


def get_price_forecast_for_sku(sku: str, days_ahead: int = 7) -> str:
    """
    Obtém previsões de PREÇO futuro usando modelo de Machine Learning.

    SEGURANÇA: Valida que o SKU pertence ao tenant atual.

    Use para analisar tendências de preço para decidir momento de compra.

    Args:
        sku: SKU do produto
        days_ahead: Número de dias à frente (padrão: 7)

    Returns:
        str: JSON com previsões de preço, datas e métricas
    """
    import asyncio

    async def _query():
        tenant_id = TenantContext.get_current_tenant()

        # Primeiro valida que SKU pertence ao tenant
        async with TenantAwareSession() as session:
            query = select(Produto).where(Produto.sku == sku)
            if tenant_id:
                query = query.where(Produto.tenant_id == tenant_id)

            result = await session.execute(query)
            produto = result.scalar_one_or_none()

            if not produto:
                return json.dumps({
                    "error": f"Produto SKU {sku} não encontrado ou não pertence ao seu tenant",
                    "access_denied": True
                }, ensure_ascii=False)

        # Se validou, chama serviço de ML
        try:
            from app.ml.prediction import predict_prices_for_product
            result = predict_prices_for_product(sku=sku, days_ahead=days_ahead)

            if "error" in result:
                return json.dumps({"error": result["error"]}, ensure_ascii=False)

            prices = result.get("prices", [])
            if len(prices) >= 2:
                trend = "alta" if prices[-1] > prices[0] else "baixa"
                var_percent = ((prices[-1] - prices[0]) / prices[0]) * 100
            else:
                trend = "estável"
                var_percent = 0.0

            return json.dumps({
                "sku": sku,
                "previsoes": prices,
                "datas": result.get("dates", []),
                "tendencia": trend,
                "variacao_percentual": round(var_percent, 2),
                "modelo_usado": result.get("model_used", "desconhecido"),
                "metricas": result.get("metrics", {})
            }, ensure_ascii=False)

        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    try:
        return asyncio.run(_query())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_query())
        finally:
            loop.close()


def find_supplier_offers_for_sku(sku: str) -> str:
    """
    Busca ofertas de fornecedores para um SKU específico.

    SEGURANÇA: Filtra ofertas do tenant atual apenas.

    Args:
        sku: SKU do produto

    Returns:
        str: JSON com ofertas ordenadas por preço
    """
    import asyncio

    async def _query():
        tenant_id = TenantContext.get_current_tenant()

        async with TenantAwareSession() as session:
            # Busca produto
            query = select(Produto).where(Produto.sku == sku)
            if tenant_id:
                query = query.where(Produto.tenant_id == tenant_id)

            result = await session.execute(query)
            produto = result.scalar_one_or_none()

            if not produto:
                return json.dumps({
                    "error": f"Produto {sku} não encontrado",
                }, ensure_ascii=False)

            # Busca ofertas
            ofertas_query = (
                select(OfertaProduto, Fornecedor)
                .join(Fornecedor, OfertaProduto.fornecedor_id == Fornecedor.id)
                .where(OfertaProduto.produto_id == produto.id)
                .where(OfertaProduto.estoque_disponivel > 0)
            )

            if tenant_id:
                ofertas_query = ofertas_query.where(OfertaProduto.tenant_id == tenant_id)

            ofertas_query = ofertas_query.order_by(OfertaProduto.preco_ofertado.asc())

            result = await session.execute(ofertas_query)
            ofertas = result.all()

            if not ofertas:
                return json.dumps({
                    "sku": sku,
                    "ofertas": [],
                    "mensagem": "Nenhuma oferta disponível no momento"
                }, ensure_ascii=False)

            ofertas_list = []
            for oferta, fornecedor in ofertas:
                ofertas_list.append({
                    "fornecedor": fornecedor.nome,
                    "preco": float(oferta.preco_ofertado),
                    "prazo_entrega_dias": fornecedor.prazo_entrega_dias,
                    "estoque_disponivel": oferta.estoque_disponivel,
                    "validade_oferta": oferta.validade_oferta.isoformat() if oferta.validade_oferta else None
                })

            melhor = ofertas_list[0]

            return json.dumps({
                "sku": sku,
                "produto": produto.nome,
                "total_ofertas": len(ofertas_list),
                "melhor_oferta": melhor,
                "todas_ofertas": ofertas_list
            }, ensure_ascii=False)

    try:
        return asyncio.run(_query())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_query())
        finally:
            loop.close()


def run_full_purchase_analysis(sku: str) -> str:
    """
    Executa análise completa de compra para um SKU.

    Combina: estoque atual + previsão + ofertas + recomendação.

    SEGURANÇA: Todos os dados são filtrados pelo tenant atual.

    Args:
        sku: SKU do produto

    Returns:
        str: JSON com análise completa e recomendação
    """
    # Coleta dados de várias fontes
    produto_info = get_product_info(sku)
    previsao = get_price_forecast_for_sku(sku, days_ahead=14)
    ofertas = find_supplier_offers_for_sku(sku)

    try:
        produto_data = json.loads(produto_info)
        previsao_data = json.loads(previsao)
        ofertas_data = json.loads(ofertas)
    except json.JSONDecodeError:
        return json.dumps({
            "error": "Erro ao processar dados do produto",
            "sku": sku
        }, ensure_ascii=False)

    # Verifica erros
    if "error" in produto_data:
        return produto_info

    # Monta análise
    analise = {
        "sku": sku,
        "produto": produto_data.get("nome"),
        "situacao_estoque": {
            "atual": produto_data.get("estoque_atual"),
            "minimo": produto_data.get("estoque_minimo"),
            "status": produto_data.get("status_reposicao"),
            "cobertura_dias": produto_data.get("cobertura_dias", 0)
        },
        "tendencia_preco": previsao_data.get("tendencia", "indisponível"),
        "variacao_prevista": previsao_data.get("variacao_percentual", 0),
        "melhor_oferta": ofertas_data.get("melhor_oferta"),
        "total_fornecedores": ofertas_data.get("total_ofertas", 0),
    }

    # Gera recomendação
    status = produto_data.get("status_reposicao", "OK")
    tendencia = previsao_data.get("tendencia", "estável")

    if status == "ALERTA" or status == "CRÍTICO":
        if tendencia == "alta":
            analise["recomendacao"] = "🔴 COMPRAR AGORA - Estoque baixo e preço subindo"
            analise["urgencia"] = "CRÍTICA"
        else:
            analise["recomendacao"] = "🟡 COMPRAR EM BREVE - Estoque baixo, preço estável/caindo"
            analise["urgencia"] = "ALTA"
    else:
        if tendencia == "alta":
            analise["recomendacao"] = "🟢 CONSIDERAR COMPRA - Estoque OK mas preço subindo"
            analise["urgencia"] = "MÉDIA"
        else:
            analise["recomendacao"] = "✅ AGUARDAR - Estoque OK e preço estável/caindo"
            analise["urgencia"] = "BAIXA"

    return json.dumps(analise, ensure_ascii=False, indent=2)


def create_purchase_order_tool(
    sku: str,
    quantidade: int,
    fornecedor_id: int | None = None
) -> str:
    """
    Cria uma ordem de compra para um produto.

    SEGURANÇA: A ordem é criada no tenant atual automaticamente.

    Args:
        sku: SKU do produto
        quantidade: Quantidade a comprar
        fornecedor_id: ID do fornecedor (opcional, usa melhor oferta se não informado)

    Returns:
        str: JSON com detalhes da ordem criada
    """
    import asyncio
    from datetime import datetime

    async def _create():
        tenant_id = TenantContext.get_current_tenant()

        if not tenant_id:
            return json.dumps({
                "error": "Operação de escrita requer contexto de tenant",
                "action": "Faça login novamente"
            }, ensure_ascii=False)

        async with TenantAwareSession() as session:
            # Busca produto
            query = (
                select(Produto)
                .where(Produto.sku == sku)
                .where(Produto.tenant_id == tenant_id)
            )
            result = await session.execute(query)
            produto = result.scalar_one_or_none()

            if not produto:
                return json.dumps({
                    "error": f"Produto {sku} não encontrado"
                }, ensure_ascii=False)

            # Se não informou fornecedor, busca melhor oferta
            selected_fornecedor_id = fornecedor_id
            if selected_fornecedor_id is None:
                ofertas_query = (
                    select(OfertaProduto)
                    .where(OfertaProduto.produto_id == produto.id)
                    .where(OfertaProduto.tenant_id == tenant_id)
                    .where(OfertaProduto.estoque_disponivel > 0)
                    .order_by(OfertaProduto.preco_ofertado.asc())
                    .limit(1)
                )
                result = await session.execute(ofertas_query)
                melhor_oferta = result.scalar_one_or_none()

                if melhor_oferta:
                    selected_fornecedor_id = melhor_oferta.fornecedor_id
                    preco_unitario = melhor_oferta.preco_ofertado
                else:
                    return json.dumps({
                        "error": "Nenhuma oferta disponível para este produto"
                    }, ensure_ascii=False)
            else:
                # Busca preço do fornecedor informado
                oferta_query = (
                    select(OfertaProduto)
                    .where(OfertaProduto.produto_id == produto.id)
                    .where(OfertaProduto.fornecedor_id == selected_fornecedor_id)
                    .where(OfertaProduto.tenant_id == tenant_id)
                )
                result = await session.execute(oferta_query)
                oferta = result.scalar_one_or_none()
                preco_unitario = oferta.preco_ofertado if oferta else Decimal("0.00")

            # Cria ordem de compra
            valor_total = preco_unitario * quantidade
            ordem = OrdemDeCompra(
                tenant_id=tenant_id,
                produto_id=produto.id,
                fornecedor_id=selected_fornecedor_id,
                quantidade=quantidade,
                valor=valor_total,
                status="pending",
                origem="Automática",
                data_criacao=datetime.now(UTC)
            )

            session.add(ordem)
            await session.flush()
            await session.refresh(ordem)

            return json.dumps({
                "success": True,
                "ordem_id": ordem.id,
                "produto": produto.nome,
                "sku": sku,
                "quantidade": quantidade,
                "preco_unitario": float(preco_unitario),
                "valor_total": float(valor_total),
                "status": "pending",
                "mensagem": f"Ordem #{ordem.id} criada com sucesso!"
            }, ensure_ascii=False)

    try:
        return asyncio.run(_create())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_create())
        finally:
            loop.close()


# ============================================================================
# MARKET RESEARCH TOOLS
# ============================================================================

def search_market_price(product_sku: str) -> str:
    """
    Realiza busca de preço de mercado (scraping).

    SEGURANÇA: Valida que SKU pertence ao tenant antes de executar.

    Args:
        product_sku: SKU do produto

    Returns:
        str: Preço encontrado ou mensagem de erro
    """
    import asyncio

    async def _search():
        tenant_id = TenantContext.get_current_tenant()

        # Valida acesso ao SKU
        async with TenantAwareSession() as session:
            query = select(Produto).where(Produto.sku == product_sku)
            if tenant_id:
                query = query.where(Produto.tenant_id == tenant_id)

            result = await session.execute(query)
            produto = result.scalar_one_or_none()

            if not produto:
                return f"Produto com SKU {product_sku} não encontrado ou não autorizado."

        # Se autorizado, executa scraping
        try:
            from app.services.scraping_service import scrape_and_save_price
            preco = scrape_and_save_price(produto.id)

            if preco:
                return f"Preço de mercado encontrado via scraping: R$ {preco:.2f}"
            else:
                return "Não foi possível encontrar preço de mercado no momento."
        except Exception as e:
            LOGGER.error(f"Erro no scraping para {product_sku}: {e}")
            return f"Erro ao buscar preço de mercado: {str(e)}"

    try:
        return asyncio.run(_search())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_search())
        finally:
            loop.close()


def get_forecast_tool(product_sku: str) -> str:
    """
    Obtém previsão de DEMANDA futura para um produto.

    SEGURANÇA: Valida acesso ao SKU pelo tenant.

    Args:
        product_sku: SKU do produto

    Returns:
        str: JSON com previsão de demanda
    """
    # Valida acesso
    produto_info = get_product_info(product_sku)
    if "error" in produto_info:
        return produto_info

    try:
        from app.ml.prediction import predict_prices_for_product as get_forecast
        forecast = get_forecast(product_sku)
        return json.dumps({
            "sku": product_sku,
            "demand_forecast": forecast,
            "tipo": "demanda"
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
