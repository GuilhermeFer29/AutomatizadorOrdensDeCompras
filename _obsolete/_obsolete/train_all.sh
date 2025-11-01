#!/bin/bash

# Script para treinar TODOS os 1.178 produtos
# Uso: ./train_all.sh [optuna_trials]

OPTUNA_TRIALS=${1:-10}

echo "========================================================================"
echo "🚀 TREINANDO TODOS OS 1.178 PRODUTOS"
echo "========================================================================"
echo "Optuna Trials: $OPTUNA_TRIALS"
echo "Tempo estimado: 2-4 horas"
echo "========================================================================"
echo ""

cd /app

python scripts/start_pipeline.py \
  --validate \
  --train \
  --optuna-trials $OPTUNA_TRIALS

if [ $? -eq 0 ]; then
  echo ""
  echo "========================================================================"
  echo "✅ TREINAMENTO COMPLETO CONCLUÍDO COM SUCESSO!"
  echo "========================================================================"
  echo ""
  echo "Próximos passos:"
  echo "1. Acessar http://localhost:3000"
  echo "2. Fazer login"
  echo "3. Visualizar dashboard com modelos treinados"
  echo ""
else
  echo ""
  echo "========================================================================"
  echo "❌ ERRO NO TREINAMENTO"
  echo "========================================================================"
  exit 1
fi
