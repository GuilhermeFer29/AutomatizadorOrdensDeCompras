#!/usr/bin/env python3
"""
🚀 TREINO COMPLETO - TODAS AS FASES (v4.0)

Executa automaticamente:
- Fase 1: 1 SKU × 5 targets (1-2h)
- Fase 2: 10 SKUs × 8 targets (2-4h)
- Fase 3: Todos os SKUs × 8 targets (4-6h)

Com TODAS as otimizações implementadas:
✅ Aumentar trials: 7 → 50
✅ Feature engineering específico por target
✅ Transforms (log1p, winsorization, clipping)
✅ Hiperparâmetros otimizados
✅ Estrutura de diretórios por target
"""

import os
import sys
import subprocess
import time
from datetime import datetime
from pathlib import Path

# Cores para output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text:^80}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.END}\n")

def print_phase(phase_num, title, duration):
    print(f"\n{Colors.CYAN}{Colors.BOLD}[FASE {phase_num}] {title} ({duration}){Colors.END}")
    print(f"{Colors.CYAN}{'-'*80}{Colors.END}\n")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def run_command(cmd, description):
    """Executa comando e mostra progresso"""
    print_info(f"Executando: {description}")
    print(f"{Colors.BLUE}$ {' '.join(cmd)}{Colors.END}\n")
    
    start_time = time.time()
    result = subprocess.run(cmd, cwd="/home/guilhermedev/Documentos/Automação Inteligente de Ordens de Compra para Pequenas e Médias Indústrias")
    elapsed = time.time() - start_time
    
    if result.returncode == 0:
        print_success(f"{description} concluído em {elapsed:.1f}s")
        return True
    else:
        print_error(f"{description} falhou com código {result.returncode}")
        return False

def main():
    print_header("🚀 TREINO COMPLETO - TODAS AS FASES")
    
    print(f"""
{Colors.BOLD}OBJETIVO:{Colors.END}
Treinar TODOS os 8 targets com otimizações completas

{Colors.BOLD}TARGETS:{Colors.END}
1. quantidade  - Demanda (MAPE < 12%)
2. preco       - Preço (MAPE < 8%)
3. receita     - Faturamento (MAPE < 10%)
4. lucro       - Lucro bruto (MAPE < 18%)
5. margem      - Margem % (MAPE < 12%)
6. custo       - Custo total (MAPE < 12%)
7. rotatividade - Giro de estoque (MAPE < 20%)
8. dias_estoque - Dias em estoque (MAPE < 25%)

{Colors.BOLD}MELHORIAS IMPLEMENTADAS:{Colors.END}
✅ Aumentar trials: 7 → 50
✅ Feature engineering específico por target
✅ Transforms (log1p, winsorization, clipping)
✅ Hiperparâmetros otimizados
✅ Estrutura de diretórios por target
✅ Validação cruzada temporal
✅ GPU (RTX 2060) utilizada eficientemente

{Colors.BOLD}TEMPO ESTIMADO:{Colors.END}
- Fase 1: 1-2 horas
- Fase 2: 2-4 horas
- Fase 3: 4-6 horas
- TOTAL: 7-12 horas
    """)
    
    input(f"\n{Colors.YELLOW}Pressione ENTER para começar...{Colors.END}\n")
    
    all_targets = "quantidade,preco,receita,lucro,margem,custo,rotatividade,dias_estoque"
    main_targets = "quantidade,preco,receita,lucro,margem"
    
    # ============================================================================
    # FASE 1: Teste com 1 SKU × 5 targets
    # ============================================================================
    print_phase(1, "TESTE RÁPIDO - 1 SKU × 5 targets", "1-2 horas")
    
    cmd_fase1 = [
        "docker-compose", "exec", "-T", "api", "python",
        "scripts/train_advanced_models.py",
        "--sku", "386DC631",
        "--targets", main_targets,
        "--trials", "50",
        "--use-all-data",
        "--no-backtest"
    ]
    
    if not run_command(cmd_fase1, "Fase 1 - Teste com 1 SKU"):
        print_error("Fase 1 falhou!")
        return False
    
    print_success("Fase 1 concluída com sucesso!")
    
    # ============================================================================
    # FASE 2: Teste com 10 SKUs × 8 targets
    # ============================================================================
    print_phase(2, "TESTE MÉDIO - 10 SKUs × 8 targets", "2-4 horas")
    
    cmd_fase2 = [
        "docker-compose", "exec", "-T", "api", "python",
        "scripts/train_advanced_models.py",
        "--limit", "10",
        "--targets", all_targets,
        "--trials", "50",
        "--use-all-data"
    ]
    
    if not run_command(cmd_fase2, "Fase 2 - Teste com 10 SKUs"):
        print_error("Fase 2 falhou!")
        return False
    
    print_success("Fase 2 concluída com sucesso!")
    
    # ============================================================================
    # FASE 3: Treino completo - TODOS os SKUs × 8 targets
    # ============================================================================
    print_phase(3, "TREINO COMPLETO - 1.178 SKUs × 8 targets", "4-6 horas")
    
    cmd_fase3 = [
        "docker-compose", "exec", "-T", "api", "python",
        "scripts/train_advanced_models.py",
        "--targets", all_targets,
        "--trials", "50",
        "--use-all-data"
    ]
    
    if not run_command(cmd_fase3, "Fase 3 - Treino completo"):
        print_error("Fase 3 falhou!")
        return False
    
    print_success("Fase 3 concluída com sucesso!")
    
    # ============================================================================
    # RESUMO FINAL
    # ============================================================================
    print_header("✅ TODAS AS FASES CONCLUÍDAS COM SUCESSO!")
    
    print(f"""
{Colors.BOLD}RESULTADOS ESPERADOS:{Colors.END}

Fase 1 (1 SKU × 5 targets):
  - quantidade: MAPE < 12%
  - preco: MAPE < 8%
  - receita: MAPE < 10%
  - lucro: MAPE < 18% (reduzido de 33.52%)
  - margem: MAPE < 12%

Fase 2 (10 SKUs × 8 targets):
  - Todos os targets com MAPE < 20%
  - Modelos salvos em /app/model/{{sku}}/{{target}}/

Fase 3 (1.178 SKUs × 8 targets):
  - 9.424 modelos treinados
  - Todos os targets com MAPE < 25%
  - Estrutura completa pronta para produção

{Colors.BOLD}PRÓXIMOS PASSOS:{Colors.END}
1. Validar previsões no dashboard
2. Testar com dados reais
3. Documentar resultados
4. Preparar para produção

{Colors.BOLD}ARQUIVOS GERADOS:{Colors.END}
✅ /app/model/*/{{target}}/ensemble_base.pkl
✅ /app/model/*/{{target}}/meta_learner.pkl
✅ /app/model/*/{{target}}/scaler.pkl
✅ /app/model/*/{{target}}/metadata.json
✅ /app/model/*/{{target}}/training_data.parquet
    """)
    
    print_success("Treino completo finalizado!")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
