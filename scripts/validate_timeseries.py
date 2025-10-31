#!/usr/bin/env python3
"""
Validador de Séries Temporais

Verifica integridade dos dados antes do treinamento:
- Buracos de datas (vendas sem preço, preços sem venda)
- Datas no futuro
- Receita incoerente com preço
- Produtos sem dados suficientes
"""

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Tuple
from decimal import Decimal

from sqlmodel import Session, select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import engine
from app.models.models import Produto, VendasHistoricas, PrecosHistoricos


class TimeSeriesValidator:
    """Validador de integridade de séries temporais."""
    
    def __init__(self, session: Session, min_days: int = 90):
        self.session = session
        self.min_days = min_days
        self.errors = []
        self.warnings = []
        
    def validate_all(self) -> bool:
        """
        Valida todos os produtos.
        
        Returns:
            True se passou em todas as validações, False caso contrário
        """
        produtos = list(self.session.exec(select(Produto)).all())
        
        if not produtos:
            self.errors.append("ERRO CRÍTICO: Nenhum produto no banco")
            return False
        
        print(f"🔍 Validando {len(produtos)} produtos...")
        
        produtos_validos = 0
        for produto in produtos:
            if self._validate_produto(produto):
                produtos_validos += 1
        
        # Sumário
        print(f"\n{'='*70}")
        print(f"📊 SUMÁRIO DA VALIDAÇÃO")
        print(f"{'='*70}")
        print(f"✅ Produtos válidos: {produtos_validos}/{len(produtos)}")
        
        if self.warnings:
            print(f"\n⚠️  {len(self.warnings)} avisos encontrados:")
            for w in self.warnings[:10]:  # Mostrar só os primeiros 10
                print(f"   {w}")
            if len(self.warnings) > 10:
                print(f"   ... e mais {len(self.warnings) - 10} avisos")
        
        if self.errors:
            print(f"\n❌ {len(self.errors)} erros críticos encontrados:")
            for e in self.errors[:10]:
                print(f"   {e}")
            if len(self.errors) > 10:
                print(f"   ... e mais {len(self.errors) - 10} erros")
            return False
        
        print(f"\n✅ Validação concluída com sucesso!")
        return True
    
    def _validate_produto(self, produto: Produto) -> bool:
        """Valida um produto específico."""
        
        # Buscar vendas e preços
        vendas = list(self.session.exec(
            select(VendasHistoricas)
            .where(VendasHistoricas.produto_id == produto.id)
            .order_by(VendasHistoricas.data_venda)
        ).all())
        
        precos = list(self.session.exec(
            select(PrecosHistoricos)
            .where(PrecosHistoricos.produto_id == produto.id)
            .order_by(PrecosHistoricos.coletado_em)
        ).all())
        
        # 1. Verificar dados mínimos
        if len(vendas) < self.min_days:
            self.warnings.append(
                f"{produto.sku}: Apenas {len(vendas)} dias de vendas (mínimo {self.min_days})"
            )
            return False
        
        if len(precos) < self.min_days:
            self.warnings.append(
                f"{produto.sku}: Apenas {len(precos)} dias de preços (mínimo {self.min_days})"
            )
            return False
        
        # 2. Verificar datas no futuro
        now = datetime.now(timezone.utc)
        
        # Garantir que comparação seja entre aware datetimes
        vendas_futuro = [
            v for v in vendas 
            if (v.data_venda.replace(tzinfo=timezone.utc) if v.data_venda.tzinfo is None else v.data_venda) > now
        ]
        precos_futuro = [
            p for p in precos 
            if (p.coletado_em.replace(tzinfo=timezone.utc) if p.coletado_em.tzinfo is None else p.coletado_em) > now
        ]
        
        if vendas_futuro:
            self.errors.append(
                f"{produto.sku}: {len(vendas_futuro)} vendas com data no futuro"
            )
        
        if precos_futuro:
            self.errors.append(
                f"{produto.sku}: {len(precos_futuro)} preços com data no futuro"
            )
        
        # 3. Verificar buracos de datas
        # Garantir que temos datas (remover timezone se houver)
        datas_vendas = {
            v.data_venda.date() if hasattr(v.data_venda, 'date') else v.data_venda
            for v in vendas
        }
        datas_precos = {
            p.coletado_em.date() if hasattr(p.coletado_em, 'date') else p.coletado_em
            for p in precos
        }
        
        # Intervalo completo
        if vendas and precos:
            # Extrair datas garantindo que sejam date objects
            vendas_dates = [
                v.data_venda.date() if hasattr(v.data_venda, 'date') else v.data_venda
                for v in vendas
            ]
            precos_dates = [
                p.coletado_em.date() if hasattr(p.coletado_em, 'date') else p.coletado_em
                for p in precos
            ]
            
            min_date = min(min(vendas_dates), min(precos_dates))
            max_date = max(max(vendas_dates), max(precos_dates))
            
            # Gerar todas as datas esperadas
            current = min_date
            missing_vendas = []
            missing_precos = []
            
            while current <= max_date:
                if current not in datas_vendas:
                    missing_vendas.append(current)
                if current not in datas_precos:
                    missing_precos.append(current)
                current += timedelta(days=1)
            
            if len(missing_vendas) > 5:
                self.warnings.append(
                    f"{produto.sku}: {len(missing_vendas)} dias sem vendas"
                )
            
            if len(missing_precos) > 5:
                self.warnings.append(
                    f"{produto.sku}: {len(missing_precos)} dias sem preço"
                )
        
        # 4. Verificar receita coerente com preço
        for venda in vendas[:10]:  # Amostrar primeiros 10
            data_venda = venda.data_venda.date()
            
            # Buscar preço do mesmo dia
            preco_dia = next(
                (p for p in precos if p.coletado_em.date() == data_venda),
                None
            )
            
            if preco_dia:
                receita_esperada = Decimal(venda.quantidade) * preco_dia.preco
                diferenca = abs(venda.receita - receita_esperada)
                
                # Tolerar 1% de diferença (arredondamento)
                if diferenca > receita_esperada * Decimal("0.01"):
                    self.errors.append(
                        f"{produto.sku}: Receita incoerente em {data_venda} "
                        f"(receita={venda.receita}, esperado={receita_esperada:.2f})"
                    )
        
        return True


def validate_timeseries(min_days: int = 90) -> bool:
    """
    Valida integridade das séries temporais.
    
    Args:
        min_days: Número mínimo de dias de dados por produto
    
    Returns:
        True se passou na validação, False caso contrário
    """
    print(f"\n{'='*70}")
    print(f"🔍 VALIDAÇÃO DE SÉRIES TEMPORAIS")
    print(f"{'='*70}\n")
    
    with Session(engine) as session:
        validator = TimeSeriesValidator(session, min_days=min_days)
        return validator.validate_all()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Valida integridade de séries temporais")
    parser.add_argument(
        "--min-days",
        type=int,
        default=90,
        help="Número mínimo de dias de dados por produto (padrão: 90)"
    )
    
    args = parser.parse_args()
    
    success = validate_timeseries(min_days=args.min_days)
    sys.exit(0 if success else 1)
