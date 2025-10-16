"""
Script CLI para treinar modelos LightGBM individuais para todos os produtos.

ARQUITETURA NOVA (2025-10-16):
===============================
✅ Treina um modelo especializado para cada produto
✅ Usa feature engineering avançado
✅ Otimização de hiperparâmetros com Optuna (opcional)
✅ Processamento paralelo (opcional)
✅ Relatório detalhado de resultados
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

import structlog
from sqlmodel import Session, select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

from app.core.database import engine
from app.ml.training import InsufficientDataError, train_model_for_product
from app.models.models import Produto

LOGGER = structlog.get_logger(__name__)


def get_all_product_skus() -> List[str]:
    """Retorna lista de todos os SKUs de produtos."""
    with Session(engine) as session:
        produtos = list(session.exec(select(Produto)).all())
        return [p.sku for p in produtos]


def train_all_products(
    skus: List[str],
    optimize: bool = True,
    n_trials: int = 50,
    skip_errors: bool = True,
) -> dict:
    """Treina modelos para uma lista de SKUs."""
    print(f"\n{'='*70}")
    print(f"TREINAMENTO DE MODELOS INDIVIDUAIS POR PRODUTO")
    print(f"{'='*70}")
    print(f"\nProdutos: {len(skus)}")
    print(f"Otimização Optuna: {'Sim' if optimize else 'Não'}")
    if optimize:
        print(f"Trials por modelo: {n_trials}")
    print(f"\n{'='*70}\n")
    
    results = {"success": [], "failed": [], "skipped": []}
    
    for idx, sku in enumerate(skus, 1):
        print(f"\n[{idx}/{len(skus)}] Treinando modelo para: {sku}")
        print("-" * 70)
        
        try:
            result = train_model_for_product(
                sku=sku, optimize=optimize, n_trials=n_trials
            )
            
            print(f"✅ Sucesso\!")
            print(f"   - Amostras treino: {result['training_samples']}")
            print(f"   - Métricas: RMSE={result['metrics']['rmse']:.4f}")
            results["success"].append(sku)
        
        except InsufficientDataError as e:
            print(f"⚠️  Pulado: {e}")
            results["skipped"].append(sku)
            if not skip_errors:
                raise
        
        except Exception as e:
            print(f"❌ Erro: {e}")
            results["failed"].append(sku)
            if not skip_errors:
                raise
    
    return results


def print_summary(results: dict):
    """Imprime resumo dos resultados."""
    total = len(results["success"]) + len(results["failed"]) + len(results["skipped"])
    
    print(f"\n\n{'='*70}")
    print("RESUMO DO TREINAMENTO")
    print(f"{'='*70}")
    print(f"\n📊 Estatísticas:")
    print(f"   - Total: {total}")
    print(f"   - ✅ Treinados: {len(results['success'])}")
    print(f"   - ⚠️  Pulados: {len(results['skipped'])}")
    print(f"   - ❌ Falharam: {len(results['failed'])}")
    print(f"\n{'='*70}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Treina modelos para todos os produtos")
    parser.add_argument("--no-optimize", action="store_true")
    parser.add_argument("--trials", type=int, default=50)
    parser.add_argument("--sku", type=str)
    parser.add_argument("--stop-on-error", action="store_true")
    
    args = parser.parse_args()
    load_dotenv()
    
    try:
        if args.sku:
            skus = [args.sku]
        else:
            skus = get_all_product_skus()
            if not skus:
                print("❌ Nenhum produto encontrado.")
                sys.exit(1)
        
        results = train_all_products(
            skus=skus,
            optimize=not args.no_optimize,
            n_trials=args.trials,
            skip_errors=not args.stop_on_error,
        )
        
        print_summary(results)
        
        if results["failed"] and args.stop_on_error:
            sys.exit(1)
        elif not results["success"]:
            sys.exit(1)
    
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
