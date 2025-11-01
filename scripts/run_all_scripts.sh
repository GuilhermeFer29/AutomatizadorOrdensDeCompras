#!/bin/bash
# Script para executar o pipeline completo de setup e treinamento
# Automação Inteligente de Ordens de Compra
#
# Executa todos os scripts em ordem:
# 1. reset_env.py
# 2. create_tables.py
# 3. seed_database.py
# 4. generate_realistic_data.py
# 5. validate_timeseries.py
# 6. train_advanced_models.py

set -e  # Parar execução se qualquer comando falhar

# Diretório do projeto
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Cores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "=========================================="
echo -e "${BLUE}Pipeline Completo de Setup e Treinamento${NC}"
echo "=========================================="
echo ""

# Executar o pipeline unificado com todos os parâmetros
echo -e "${BLUE}Executando pipeline completo...${NC}"
echo ""

python3 scripts/start_pipeline.py \
    --reset \
    --seed-products \
    --days 365 \
    --generate-prices \
    --generate-sales \
    --validate \
    --train

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo -e "${GREEN}✅ Pipeline executado com sucesso!${NC}"
    echo "=========================================="
    echo ""
    echo "Próximos passos:"
    echo "  1. Verifique os modelos em: models/"
    echo "  2. Inicie a API: uvicorn app.main:app --reload"
    echo "  3. Acesse a documentação: http://localhost:8000/docs"
    echo ""
else
    echo ""
    echo -e "${RED}❌ Pipeline falhou. Verifique os logs acima.${NC}"
    echo ""
    exit 1
fi
