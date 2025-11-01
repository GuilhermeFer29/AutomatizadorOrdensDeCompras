#!/bin/bash

# Script rápido para executar testes sem instalar dependências
# Uso: docker-compose exec -T api bash scripts/test_fast.sh

set -e

echo "🧪 Executando testes..."
echo "================================"

# Cores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Executar testes com cobertura
echo -e "${BLUE}📊 Rodando testes com cobertura...${NC}"
pytest app/tests/ -v --tb=short --cov=app --cov-report=term-missing --cov-report=html

echo ""
echo -e "${GREEN}✅ Testes concluídos!${NC}"
echo "================================"
echo -e "${GREEN}📊 Relatório HTML: htmlcov/index.html${NC}"
