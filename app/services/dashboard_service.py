"""
Dashboard Service - KPIs e Alertas Reais do Sistema

Este serviço fornece dados reais para o dashboard do frontend,
calculando métricas a partir do banco de dados.
"""

import json
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import and_
from sqlmodel import Session, func, select

from app.core.config import ROOT_DIR
from app.models.models import OfertaProduto, OrdemDeCompra, PrecosHistoricos, Produto

logger = logging.getLogger(__name__)


def get_dashboard_kpis(session: Session) -> dict[str, Any]:
    """
    Calcula KPIs reais do sistema para o dashboard.

    Returns:
        Dict com:
        - economy: Economia estimada (diferença entre preço médio e melhor oferta)
        - automatedOrders: Número de ordens automáticas aprovadas
        - stockLevel: Nível do estoque (Crítico, Atenção, Saudável)
        - modelAccuracy: Acurácia do modelo ML (baseado em MAPE)
    """

    # 1. ECONOMIA ESTIMADA
    # Calcula a diferença entre o preço médio histórico e a melhor oferta atual
    total_economy = Decimal("0.00")

    try:
        # Buscar produtos com ofertas
        produtos_com_ofertas = session.exec(
            select(Produto).where(
                Produto.id.in_(
                    select(OfertaProduto.produto_id).distinct()
                )
            )
        ).all()

        for produto in produtos_com_ofertas:
            # Preço médio dos últimos 30 dias
            data_limite = datetime.now(UTC) - timedelta(days=30)
            precos = list(session.exec(
                select(PrecosHistoricos.preco)
                .where(PrecosHistoricos.produto_id == produto.id)
                .where(PrecosHistoricos.coletado_em >= data_limite)
            ).all())

            if precos:
                preco_medio = sum(precos) / len(precos)

                # Melhor oferta atual
                melhor_oferta = session.exec(
                    select(func.min(OfertaProduto.preco_ofertado))
                    .where(OfertaProduto.produto_id == produto.id)
                ).one_or_none()

                if melhor_oferta and melhor_oferta < preco_medio:
                    economia_produto = (preco_medio - melhor_oferta) * produto.estoque_atual
                    total_economy += economia_produto

    except Exception as e:
        logger.warning(f"Erro ao calcular economia: {e}")
        total_economy = Decimal("0.00")

    # 2. ORDENS AUTOMATIZADAS
    # Conta ordens criadas pelo chat/agente (não manuais)
    automated_orders = 0
    try:
        automated_count = session.exec(
            select(func.count(OrdemDeCompra.id))
            .where(
                OrdemDeCompra.origem.in_(["Automática", "Chat", "Agente", "Chat - Aprovação Automática"])
            )
        ).one_or_none()
        automated_orders = automated_count or 0
    except Exception as e:
        logger.warning(f"Erro ao contar ordens automáticas: {e}")

    # 3. NÍVEL DE ESTOQUE
    # Calcula percentual de produtos com estoque saudável
    stock_level = "Saudável"
    stock_percentage = 100.0

    try:
        total_products = session.exec(select(func.count(Produto.id))).one_or_none() or 0

        if total_products > 0:
            # Produtos com estoque abaixo do mínimo
            critical_count = session.exec(
                select(func.count(Produto.id))
                .where(Produto.estoque_atual < Produto.estoque_minimo)
            ).one_or_none() or 0

            # Produtos com estoque até 1.5x o mínimo (atenção)
            attention_count = session.exec(
                select(func.count(Produto.id))
                .where(
                    and_(
                        Produto.estoque_atual >= Produto.estoque_minimo,
                        Produto.estoque_atual < Produto.estoque_minimo * 1.5
                    )
                )
            ).one_or_none() or 0

            # Percentual de produtos com estoque OK
            healthy_count = total_products - critical_count - attention_count
            stock_percentage = (healthy_count / total_products) * 100

            if critical_count > 0:
                if (critical_count / total_products) > 0.3:
                    stock_level = "Crítico"
                else:
                    stock_level = "Atenção"
            elif attention_count > total_products * 0.3:
                stock_level = "Atenção"
            else:
                stock_level = "Saudável"

        logger.info(f"📊 Estoque: {stock_level} ({stock_percentage:.1f}% saudável)")

    except Exception as e:
        logger.warning(f"Erro ao calcular nível de estoque: {e}")

    # 4. ACURÁCIA DO MODELO ML
    # Baseado em MAPE: 100% - MAPE = Acurácia
    model_accuracy = 0.0

    try:
        # Tentar ler métricas do modelo global
        metadata_path = ROOT_DIR / "models" / "global_lgbm_metadata.json"
        if metadata_path.exists():
            with open(metadata_path) as f:
                metadata = json.load(f)
                mape = metadata.get("metrics", {}).get("mape", 0.0)
                # Acurácia = 100% - MAPE (limitado a 0-100%)
                model_accuracy = max(0, min(100, 100 - mape)) / 100
        else:
            # Fallback: usar média simples se não houver modelo treinado
            # Indicar que o modelo não foi treinado
            model_accuracy = 0.0
            logger.info("⚠️ Modelo ML não encontrado - exibindo 0%")

    except Exception as e:
        logger.warning(f"Erro ao ler métricas do modelo: {e}")

    return {
        "economy": float(total_economy),
        "automatedOrders": automated_orders,
        "stockLevel": stock_level,
        "modelAccuracy": model_accuracy,
        # Campos extras para debugging (opcional)
        "_debug": {
            "stockPercentage": stock_percentage,
            "totalProducts": total_products if 'total_products' in dir() else 0,
        }
    }


def get_dashboard_alerts(session: Session) -> list[dict[str, Any]]:
    """
    Retorna alertas de produtos que precisam de atenção.

    Tipos de alertas:
    - error: Estoque abaixo do mínimo (crítico)
    - warning: Estoque próximo do mínimo (atenção)
    - success: Sem vendas recentes (pode indicar problema)

    Returns:
        Lista de alertas ordenada por severidade
    """
    alerts = []

    try:
        # 1. ALERTA CRÍTICO: Estoque abaixo do mínimo
        low_stock_products = session.exec(
            select(Produto)
            .where(Produto.estoque_atual < Produto.estoque_minimo)
            .order_by(Produto.estoque_atual)  # Mais crítico primeiro
            .limit(10)  # Limitar para não sobrecarregar UI
        ).all()

        for product in low_stock_products:
            deficit = product.estoque_minimo - product.estoque_atual
            alerts.append({
                "id": product.id,
                "product": product.nome,
                "sku": product.sku,
                "alert": f"Estoque crítico! Faltam {deficit} unidades",
                "stock": product.estoque_atual,
                "minStock": product.estoque_minimo,
                "severity": "error",
            })

        # 2. ALERTA DE ATENÇÃO: Estoque próximo do mínimo (< 1.5x)
        attention_products = session.exec(
            select(Produto)
            .where(
                and_(
                    Produto.estoque_atual >= Produto.estoque_minimo,
                    Produto.estoque_atual < Produto.estoque_minimo * 1.5
                )
            )
            .order_by(Produto.estoque_atual)
            .limit(5)
        ).all()

        for product in attention_products:
            margin = product.estoque_atual - product.estoque_minimo
            alerts.append({
                "id": product.id,
                "product": product.nome,
                "sku": product.sku,
                "alert": f"Estoque em atenção (margem: {margin} un)",
                "stock": product.estoque_atual,
                "minStock": product.estoque_minimo,
                "severity": "warning",
            })

        # 3. ALERTA INFO: Ordens pendentes aguardando aprovação
        pending_orders = session.exec(
            select(func.count(OrdemDeCompra.id))
            .where(OrdemDeCompra.status == "pending")
        ).one_or_none() or 0

        if pending_orders > 0:
            alerts.append({
                "id": 0,
                "product": f"{pending_orders} ordem(s)",
                "sku": "-",
                "alert": "Ordens pendentes aguardando aprovação",
                "stock": pending_orders,
                "minStock": 0,
                "severity": "warning" if pending_orders > 3 else "success",
            })

        logger.info(f"📋 Alertas gerados: {len(alerts)} (críticos: {len(low_stock_products)})")

    except Exception as e:
        logger.error(f"Erro ao gerar alertas: {e}")

    # Ordenar por severidade (error > warning > success)
    severity_order = {"error": 0, "warning": 1, "success": 2}
    alerts.sort(key=lambda x: severity_order.get(x["severity"], 3))

    return alerts


def get_dashboard_summary(session: Session) -> dict[str, Any]:
    """
    Retorna um resumo completo do sistema para o dashboard.
    Combina KPIs e alertas em uma única resposta.
    """
    return {
        "kpis": get_dashboard_kpis(session),
        "alerts": get_dashboard_alerts(session),
        "timestamp": datetime.now(UTC).isoformat(),
    }
