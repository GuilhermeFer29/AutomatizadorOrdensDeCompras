#!/usr/bin/env python3
"""
Script para executar testes dentro do container Docker
Uso: python scripts/run_tests.py
"""

import subprocess
import sys
import os
from pathlib import Path

# Cores para output
GREEN = '\033[0;32m'
BLUE = '\033[0;34m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
NC = '\033[0m'  # No Color

def print_header(text):
    """Imprime um cabeçalho formatado"""
    print(f"\n{BLUE}{'='*60}{NC}")
    print(f"{BLUE}{text}{NC}")
    print(f"{BLUE}{'='*60}{NC}\n")

def print_section(text):
    """Imprime uma seção formatada"""
    print(f"\n{YELLOW}📝 {text}{NC}")
    print(f"{YELLOW}{'-'*60}{NC}\n")

def run_command(cmd, description):
    """Executa um comando e retorna o status"""
    print(f"{BLUE}▶ {description}...{NC}")
    result = subprocess.run(cmd, shell=True)
    return result.returncode == 0

def main():
    """Função principal"""
    print_header("🧪 SUITE DE TESTES - Automação Inteligente de Ordens de Compra")
    
    # Verificar se está no diretório correto
    if not Path("app/tests").exists():
        print(f"{RED}❌ Erro: Diretório app/tests não encontrado!{NC}")
        print(f"{RED}Execute este script da raiz do projeto.{NC}")
        sys.exit(1)
    
    # 1. Instalar dependências de teste
    print_section("Instalando dependências de teste")
    if not run_command(
        "pip install -q pytest pytest-asyncio pytest-cov httpx",
        "Instalando pytest e dependências"
    ):
        print(f"{YELLOW}⚠️ Aviso: Algumas dependências podem não ter sido instaladas{NC}")
    
    # 2. Executar testes de autenticação
    print_section("Testes de Autenticação")
    auth_success = run_command(
        "pytest app/tests/test_auth.py -v --tb=short",
        "Executando testes de autenticação"
    )
    
    # 3. Executar testes de ordens
    print_section("Testes de Ordens")
    orders_success = run_command(
        "pytest app/tests/test_orders.py -v --tb=short",
        "Executando testes de ordens"
    )
    
    # 4. Executar todos os testes com cobertura
    print_section("Relatório de Cobertura")
    coverage_success = run_command(
        "pytest app/tests/ --cov=app --cov-report=term-missing --cov-report=html",
        "Gerando relatório de cobertura"
    )
    
    # Resumo final
    print_header("📊 RESUMO DOS TESTES")
    
    results = {
        "Autenticação": auth_success,
        "Ordens": orders_success,
        "Cobertura": coverage_success
    }
    
    for test_name, success in results.items():
        status = f"{GREEN}✅ PASSOU{NC}" if success else f"{RED}❌ FALHOU{NC}"
        print(f"{test_name:20} {status}")
    
    print()
    
    if all(results.values()):
        print(f"{GREEN}{'='*60}{NC}")
        print(f"{GREEN}✅ TODOS OS TESTES PASSARAM!{NC}")
        print(f"{GREEN}{'='*60}{NC}")
        print(f"\n{BLUE}📊 Relatório HTML: htmlcov/index.html{NC}\n")
        return 0
    else:
        print(f"{RED}{'='*60}{NC}")
        print(f"{RED}❌ ALGUNS TESTES FALHARAM!{NC}")
        print(f"{RED}{'='*60}{NC}\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
