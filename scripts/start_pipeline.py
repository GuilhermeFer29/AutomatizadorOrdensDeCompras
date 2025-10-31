#!/usr/bin/env python3
"""
Pipeline Unificado de Dados e Treinamento

Este é o ÚNICO ponto de entrada para:
1. Resetar/criar banco
2. Popular produtos
3. Gerar preços (PrecosHistoricos.coletado_em)
4. Gerar vendas (VendasHistoricas.data_venda) com receita coerente
5. Validar séries temporais
6. Treinar modelos ML

USO:
    # Pipeline completo
    python start_pipeline.py --reset --seed-products --days 365 \\
        --generate-prices --generate-sales --validate --train

    # Apenas validação e treino
    python start_pipeline.py --validate --train --optuna-trials 20

    # Apenas um produto
    python start_pipeline.py --train --sku ABC123 --no-optuna
"""

import sys
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class PipelineOrchestrator:
    """Orquestrador unificado de toda a pipeline de dados e ML."""
    
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.scripts_dir = PROJECT_ROOT / "scripts"
        self.start_time = datetime.now()
        
    def log(self, message: str, level: str = "INFO"):
        """Log padronizado."""
        if self.verbose:
            prefix = {
                "INFO": "ℹ️ ",
                "SUCCESS": "✅",
                "ERROR": "❌",
                "WARNING": "⚠️ ",
                "STEP": "▶️ ",
            }.get(level, "  ")
            print(f"{prefix} {message}")
    
    def run_script(
        self,
        script_name: str,
        args: list = None,
        check: bool = True
    ) -> bool:
        """
        Executa um script Python.
        
        Args:
            script_name: Nome do script (ex: 'create_tables.py')
            args: Lista de argumentos para o script
            check: Se True, falha se o script retornar erro
        
        Returns:
            True se sucesso, False caso contrário
        """
        script_path = self.scripts_dir / script_name
        
        if not script_path.exists():
            self.log(f"Script não encontrado: {script_path}", "ERROR")
            return False
        
        cmd = [sys.executable, str(script_path)]
        if args:
            cmd.extend(args)
        
        try:
            result = subprocess.run(
                cmd,
                check=check,
                capture_output=False,
                text=True
            )
            return result.returncode == 0
        except subprocess.CalledProcessError as e:
            self.log(f"Erro ao executar {script_name}: {e}", "ERROR")
            return False
    
    def reset_database(self) -> bool:
        """Reseta o banco de dados (cria tabelas)."""
        self.log("Resetando banco de dados...", "STEP")
        return self.run_script("create_tables.py")
    
    def seed_products(self, source: Optional[str] = None) -> bool:
        """
        Popula produtos no banco.
        
        Args:
            source: Caminho para CSV de produtos (opcional)
        """
        self.log("Populando produtos...", "STEP")
        args = []
        if source:
            args.extend(["--source", source])
        return self.run_script("seed_database.py", args)
    
    def generate_prices(
        self,
        days: int = 365,
        clear: bool = False,
        only_missing: bool = False
    ) -> bool:
        """
        Gera histórico de preços.
        
        Args:
            days: Número de dias de histórico
            clear: Limpar preços sintéticos existentes
            only_missing: Gerar apenas dias faltantes
        """
        self.log(f"Gerando {days} dias de preços...", "STEP")
        args = ["--days", str(days)]
        if clear:
            args.append("--clear")
        if only_missing:
            args.append("--only-missing")
        
        return self.run_script("generate_realistic_data.py", args)
    
    def generate_sales(
        self,
        days: int = 365,
        clear: bool = False
    ) -> bool:
        """
        Gera histórico de vendas (com receita coerente).
        
        Args:
            days: Número de dias de histórico
            clear: Limpar vendas existentes
        """
        self.log(f"Gerando {days} dias de vendas...", "STEP")
        
        # generate_realistic_data.py já gera preços E vendas
        # Então não precisa chamar separado
        # Mas se precisar, criar generate_sales_coherent.py
        self.log("Vendas já incluídas na geração de preços", "INFO")
        return True
    
    def validate_timeseries(self, min_days: int = 90) -> bool:
        """
        Valida integridade das séries temporais.
        
        Args:
            min_days: Número mínimo de dias de dados
        
        Returns:
            True se passou na validação
        """
        self.log("Validando séries temporais...", "STEP")
        args = ["--min-days", str(min_days)]
        return self.run_script("validate_timeseries.py", args, check=True)
    
    def train_models(
        self,
        sku: Optional[str] = None,
        optuna_trials: int = 20,
        no_optuna: bool = False,
        no_backtest: bool = False,
        train_limit: Optional[int] = None
    ) -> bool:
        """
        Treina modelos ML avançados.
        
        Args:
            sku: Treinar apenas um SKU específico
            optuna_trials: Número de trials do Optuna
            no_optuna: Desativar otimização de hiperparâmetros
            no_backtest: Desativar backtest deslizante
            train_limit: Limitar número de produtos a treinar
        """
        self.log("Treinando modelos ML...", "STEP")
        args = []
        
        if sku:
            args.extend(["--sku", sku])
        
        if no_optuna:
            args.append("--no-optuna")
        else:
            args.extend(["--trials", str(optuna_trials)])
        
        if no_backtest:
            args.append("--no-backtest")
        
        if train_limit:
            args.extend(["--limit", str(train_limit)])
        
        return self.run_script("train_advanced_models.py", args)
    
    def run(self, args: argparse.Namespace) -> bool:
        """
        Executa a pipeline completa.
        
        Returns:
            True se sucesso, False se falhou
        """
        print(f"\n{'='*70}")
        print(f"🚀 PIPELINE UNIFICADA DE DADOS E ML")
        print(f"{'='*70}\n")
        
        steps_completed = 0
        steps_total = sum([
            args.reset,
            args.seed_products,
            args.generate_prices,
            args.generate_sales,
            args.validate,
            args.train,
        ])
        
        # 1. Reset
        if args.reset:
            if not self.reset_database():
                self.log("Falha ao resetar banco", "ERROR")
                return False
            steps_completed += 1
        
        # 2. Seed produtos
        if args.seed_products:
            if not self.seed_products():
                self.log("Falha ao popular produtos", "ERROR")
                return False
            steps_completed += 1
        
        # 3. Gerar preços
        if args.generate_prices:
            if not self.generate_prices(
                days=args.days,
                clear=args.clear,
                only_missing=args.only_missing
            ):
                self.log("Falha ao gerar preços", "ERROR")
                return False
            steps_completed += 1
        
        # 4. Gerar vendas
        if args.generate_sales:
            if not self.generate_sales(days=args.days, clear=args.clear):
                self.log("Falha ao gerar vendas", "ERROR")
                return False
            steps_completed += 1
        
        # 5. Validar
        if args.validate:
            if not self.validate_timeseries(min_days=args.min_days):
                self.log("Validação falhou - NÃO TREINAR!", "ERROR")
                return False
            steps_completed += 1
        
        # 6. Treinar
        if args.train:
            if not self.train_models(
                sku=args.sku,
                optuna_trials=args.optuna_trials,
                no_optuna=args.no_optuna,
                no_backtest=args.no_backtest,
                train_limit=args.train_limit
            ):
                self.log("Falha ao treinar modelos", "ERROR")
                return False
            steps_completed += 1
        
        # Sumário
        elapsed = datetime.now() - self.start_time
        print(f"\n{'='*70}")
        print(f"✅ PIPELINE CONCLUÍDA COM SUCESSO!")
        print(f"{'='*70}")
        print(f"📊 Etapas concluídas: {steps_completed}/{steps_total}")
        print(f"⏱️  Tempo total: {elapsed}")
        print(f"{'='*70}\n")
        
        return True


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline unificada de dados e treinamento ML",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Pipeline completa (do zero)
  python start_pipeline.py --reset --seed-products --days 365 \\
      --generate-prices --generate-sales --validate --train

  # Apenas validação e treino
  python start_pipeline.py --validate --train --optuna-trials 20

  # Treinar apenas um produto
  python start_pipeline.py --train --sku ABC123 --no-optuna

  # Regenerar dados sem limpar
  python start_pipeline.py --generate-prices --generate-sales \\
      --only-missing --validate --train
        """
    )
    
    # Etapas da pipeline
    parser.add_argument("--reset", action="store_true",
                        help="Resetar banco (criar tabelas)")
    parser.add_argument("--seed-products", action="store_true",
                        help="Popular produtos base")
    parser.add_argument("--generate-prices", action="store_true",
                        help="Gerar histórico de preços")
    parser.add_argument("--generate-sales", action="store_true",
                        help="Gerar histórico de vendas")
    parser.add_argument("--validate", action="store_true",
                        help="Validar integridade das séries temporais")
    parser.add_argument("--train", action="store_true",
                        help="Treinar modelos ML")
    
    # Configurações gerais
    parser.add_argument("--days", type=int, default=365,
                        help="Dias de histórico a gerar (padrão: 365)")
    parser.add_argument("--clear", action="store_true",
                        help="Limpar dados sintéticos existentes")
    parser.add_argument("--only-missing", action="store_true",
                        help="Gerar apenas dias faltantes")
    parser.add_argument("--min-days", type=int, default=90,
                        help="Mínimo de dias para validação (padrão: 90)")
    
    # Configurações de treinamento
    parser.add_argument("--sku", type=str,
                        help="Treinar apenas um SKU específico")
    parser.add_argument("--optuna-trials", type=int, default=20,
                        help="Número de trials do Optuna (padrão: 20)")
    parser.add_argument("--no-optuna", action="store_true",
                        help="Desativar otimização de hiperparâmetros")
    parser.add_argument("--no-backtest", action="store_true",
                        help="Desativar backtest deslizante")
    parser.add_argument("--train-limit", type=int,
                        help="Limitar número de produtos a treinar")
    
    # Outros
    parser.add_argument("--quiet", action="store_true",
                        help="Modo silencioso (menos logs)")
    
    args = parser.parse_args()
    
    # Se nenhuma flag foi passada, mostrar help
    if not any([
        args.reset, args.seed_products, args.generate_prices,
        args.generate_sales, args.validate, args.train
    ]):
        parser.print_help()
        sys.exit(1)
    
    # Executar pipeline
    orchestrator = PipelineOrchestrator(verbose=not args.quiet)
    success = orchestrator.run(args)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
