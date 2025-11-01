#!/bin/bash

# Script para executar testes dentro do container Docker
# Uso: docker-compose exec api bash scripts/run_tests.sh

set -e

echo "🧪 Iniciando testes..."
echo "================================"

# Cores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Instalar dependências de teste se necessário
echo -e "${BLUE}📦 Verificando dependências de teste...${NC}"
pip install -q pytest pytest-asyncio pytest-cov httpx 2>/dev/null || true

# 2. Executar testes com cobertura
echo -e "${BLUE}🧪 Executando testes...${NC}"
echo ""

# Testes de autenticação
echo -e "${YELLOW}📝 Testes de Autenticação${NC}"
pytest app/tests/test_auth.py -v --tb=short

echo ""

# Testes de ordens
echo -e "${YELLOW}📝 Testes de Ordens${NC}"
pytest app/tests/test_orders.py -v --tb=short

echo ""

# Relatório de cobertura
echo -e "${BLUE}📊 Gerando relatório de cobertura...${NC}"
pytest app/tests/ --cov=app --cov-report=term-missing --cov-report=html

echo ""
echo -e "${GREEN}✅ Testes concluídos!${NC}"
echo "================================"
echo -e "${GREEN}📊 Relatório HTML: htmlcov/index.html${NC}"
