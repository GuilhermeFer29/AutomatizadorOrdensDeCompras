# 🐳 Scripts de Banco de Dados - Execução Docker

## 📋 Scripts Disponíveis

Dois scripts estão disponíveis para operações relacionadas ao banco de dados e ChromaDB:

### 1. `script_reindex.py` ✅
**Função**: Reindexar catálogo completo de produtos no ChromaDB  
**Uso**: Migração, atualização de embeddings, reset do vector store

### 2. `fix_embeddings.py` ✅
**Função**: Corrigir/migrar embeddings e reconstruir vector store  
**Uso**: Correção de problemas, mudança de modelo de embeddings

---

## 🚀 Como Executar (Docker)

### Pré-requisitos

1. **Containers rodando**:
```bash
docker-compose up -d
```

2. **Verificar status**:
```bash
docker-compose ps
```

Certifique-se que os containers `api`, `db`, e `broker` estão **healthy**.

---

## 📦 Script 1: Reindexação do Catálogo

### Quando usar?
- ✅ Após atualizar para Gemini 2.5
- ✅ Quando adicionar novos produtos
- ✅ Após mudar modelo de embeddings
- ✅ Reset completo do ChromaDB

### Como executar:

```bash
docker-compose exec api python script_reindex.py
```

### Output esperado:

```
════════════════════════════════════════════════════════════════════════════════
  REINDEXAÇÃO DO CATÁLOGO DE PRODUTOS
  LangChain + Google AI Embeddings (text-embedding-004)
════════════════════════════════════════════════════════════════════════════════

🔍 Validando ambiente...

✅ GOOGLE_API_KEY: AIza****abc123
✅ Dependências importadas
✅ Banco de dados: 150 produtos encontrados

📁 Verificando diretório ChromaDB...

⚠️ Diretório ChromaDB existe: /app/data/chroma
   Contém 45 arquivos

🔄 Recomendação: Delete o diretório antigo para evitar conflitos
   (A reindexação criará uma nova versão)

❓ Deseja deletar o ChromaDB existente? [s/N]: s
✅ Diretório deletado: /app/data/chroma

────────────────────────────────────────────────────────────────────────────────

🎯 PRONTO PARA REINDEXAR

   Isso irá:
   • Carregar todos os produtos do banco de dados
   • Gerar embeddings usando Google text-embedding-004
   • Armazenar no ChromaDB para busca semântica

❓ Continuar com a reindexação? [S/n]: s

────────────────────────────────────────────────────────────────────────────────

🚀 Iniciando reindexação...

✅ [RAG Service] 150 produtos indexados com embeddings Google AI

✅ Reindexação concluída em 12.34 segundos!

🔍 Verificando indexação...

📝 Query de teste: 'Me mostre os produtos disponíveis'

✅ Teste de busca RAG: PASSOU

📋 Resposta de exemplo (300 caracteres):
────────────────────────────────────────────────────────────────────────────────
Encontrei 150 produtos no catálogo. Aqui estão alguns exemplos:

1. Parafusadeira Makita (SKU_005): 45 unidades em estoque
2. Serra Circular Bosch (SKU_012): 28 unidades em estoque
3. Furadeira DeWalt (SKU_023): 67 unidades em estoque
...
────────────────────────────────────────────────────────────────────────────────

════════════════════════════════════════════════════════════════════════════════
  ✅ REINDEXAÇÃO CONCLUÍDA COM SUCESSO!
════════════════════════════════════════════════════════════════════════════════

📝 Próximos passos:
   1. Verifique os logs acima
   2. Teste o assistente conversacional
   3. Monitore performance das buscas
```

---

## 🔧 Script 2: Correção de Embeddings

### Quando usar?
- ✅ Erro de dimensões incompatíveis
- ✅ Migração de modelo de embeddings
- ✅ ChromaDB corrompido
- ✅ Problemas de busca semântica

### Como executar:

```bash
docker-compose exec api python fix_embeddings.py
```

### Output esperado:

```
════════════════════════════════════════════════════════════════════════════════
Script de Correção: Limpa ChromaDB e reconstrói embeddings
════════════════════════════════════════════════════════════════════════════════

⚠️ Este script irá:
   1. Deletar COMPLETAMENTE o diretório ChromaDB
   2. Reindexar todos os produtos com embeddings Google AI
   3. Reconstruir o vector store do zero

❓ Deseja continuar? [s/N]: s

🗑️ Deletando ChromaDB antigo...
✅ Diretório /app/data/chroma deletado

📊 Reindexando produtos...
✅ [RAG Service] 150 produtos indexados com embeddings Google AI

✅ Correção concluída com sucesso!
```

---

## 🔍 Validação dos Scripts

### Verificar ChromaDB após reindexação:

```bash
docker-compose exec api ls -lah /app/data/chroma
```

**Output esperado**: Diretório com arquivos `.parquet`, `.sqlite`, etc.

### Testar RAG Service:

```bash
docker-compose exec api python -c "
from app.services.rag_service import query_product_catalog_with_google_rag
result = query_product_catalog_with_google_rag('Quais produtos temos?')
print(result[:200])
"
```

**Output esperado**: Resposta com lista de produtos do catálogo.

### Verificar modelo de embeddings:

```bash
docker-compose exec api python -c "
from app.services.rag_service import google_embeddings
print(f'Modelo: {google_embeddings.model}')
"
```

**Output esperado**: `Modelo: models/text-embedding-004`

---

## 🐛 Troubleshooting

### Problema: Container `api` não está rodando

```bash
# Verificar logs
docker-compose logs api

# Reiniciar container
docker-compose restart api
```

### Problema: Erro de permissão no ChromaDB

```bash
# Ajustar permissões do diretório
docker-compose exec api chown -R app:app /app/data/chroma

# Ou deletar e recriar
docker-compose exec api rm -rf /app/data/chroma
docker-compose exec api python script_reindex.py
```

### Problema: GOOGLE_API_KEY não encontrada

```bash
# Verificar variável de ambiente no container
docker-compose exec api env | grep GOOGLE_API_KEY

# Se vazio, adicione ao .env e reinicie
docker-compose restart api
```

### Problema: Banco de dados não responde

```bash
# Verificar status do DB
docker-compose exec db mysqladmin ping

# Reiniciar DB
docker-compose restart db

# Aguardar health check
docker-compose ps
```

### Problema: ChromaDB com dimensões incompatíveis

```bash
# Solução: Use fix_embeddings.py
docker-compose exec api python fix_embeddings.py
```

---

## 📊 Comandos Úteis Docker

### Logs em tempo real:

```bash
# Logs do container API
docker-compose logs -f api

# Logs de todos os containers
docker-compose logs -f
```

### Acessar shell do container:

```bash
docker-compose exec api bash
```

### Dentro do container, executar script diretamente:

```bash
# Após docker-compose exec api bash
python script_reindex.py
```

### Reiniciar todos os containers:

```bash
docker-compose restart
```

### Parar e remover containers:

```bash
docker-compose down
```

### Rebuild completo:

```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

---

## 📝 Fluxo Recomendado

### Após Atualização para Gemini 2.5:

```bash
# 1. Parar containers
docker-compose down

# 2. Rebuild (para pegar novas dependências)
docker-compose build

# 3. Iniciar containers
docker-compose up -d

# 4. Aguardar containers ficarem healthy
docker-compose ps

# 5. Reindexar catálogo
docker-compose exec api python script_reindex.py

# 6. Validar
docker-compose exec api python -c "
from app.services.rag_service import query_product_catalog_with_google_rag
print(query_product_catalog_with_google_rag('Listar produtos'))
"
```

---

## ⚡ Comandos Rápidos

### Reindexação rápida (sem confirmações):

```bash
docker-compose exec api python -c "
import sys
from pathlib import Path
sys.path.insert(0, '/app')
from app.core.database import engine
from app.services.rag_service import index_product_catalog
from sqlmodel import Session
with Session(engine) as session:
    index_product_catalog(session)
print('✅ Reindexação concluída')
"
```

### Limpar ChromaDB:

```bash
docker-compose exec api rm -rf /app/data/chroma
```

### Verificar quantidade de produtos:

```bash
docker-compose exec api python -c "
from app.core.database import engine
from app.models.models import Produto
from sqlmodel import Session, select
with Session(engine) as session:
    count = len(session.exec(select(Produto)).all())
print(f'Total de produtos: {count}')
"
```

---

## ✅ Checklist de Validação

Após executar os scripts, valide:

- [ ] ChromaDB existe em `/app/data/chroma`
- [ ] Logs mostram produtos indexados com sucesso
- [ ] RAG Service retorna respostas corretas
- [ ] Modelo de embeddings é `text-embedding-004`
- [ ] Sem erros nos logs do container
- [ ] Assistente conversacional funciona

---

## 🎯 Status

```
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║   ✅ SCRIPTS DE BANCO PRONTOS PARA DOCKER               ║
║                                                          ║
║   • script_reindex.py - Reindexação completa            ║
║   • fix_embeddings.py - Correção de problemas           ║
║                                                          ║
║   Execução: docker-compose exec api python <script>     ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
```

**Ambiente**: Docker Compose  
**Container**: `api`  
**Modelos**: Gemini 2.5 + text-embedding-004
