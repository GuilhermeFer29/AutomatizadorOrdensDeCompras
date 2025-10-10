# 🔍 DIAGNÓSTICO: "Não consegui identificar qual produto"

**Data:** 2025-10-09 21:15 BRT  
**Status:** 🟡 **EM INVESTIGAÇÃO**

---

## 🔴 PROBLEMA RELATADO

### Pergunta do Usuário
```
"Qual o estoque do meu produto: A vantagem de ganhar sem preocupação"
```

### Resposta do Sistema
```
Não consegui identificar qual produto você está mencionando. 
Poderia informar o SKU? (ex: SKU_001)
```

**Comportamento:** Sistema não está encontrando o produto, mesmo ele existindo no banco.

---

## ✅ VALIDAÇÕES REALIZADAS

### 1. Produto EXISTE no Banco MySQL
```bash
✅ CONFIRMADO: Produto existe!
- SKU: 84903501
- Nome: A vantagem de ganhar sem preocupação
- Banco: 200 produtos cadastrados
```

### 2. Regex de Extração FUNCIONA
```bash
✅ CONFIRMADO: Regex captura corretamente!
Pattern: produto[:\s]+(.+?)(?:\?|$)
Capturado: "a vantagem de ganhar sem preocupação"
```

### 3. Fallback FUNCIONA Perfeitamente
```bash
✅ CONFIRMADO: Fallback resolve o produto!
Input: "Qual o estoque do meu produto: A vantagem de ganhar sem preocupação"
Output: 
  - sku: 84903501
  - product_name: a vantagem de ganhar sem preocupação
  - intent: stock_check
  - confidence: medium
```

### 4. Código Atualizado ESTÁ no Container
```bash
✅ CONFIRMADO: Código novo aplicado!
- CORREÇÃO (2025-10-09) presente
- product_name_patterns presente
- resolve_product_name_to_sku presente
```

---

## 🔍 HIPÓTESE DO PROBLEMA

### Fluxo do Sistema

```
1. Usuário envia mensagem
   ↓
2. extract_entities() é chamado
   ↓
3. extract_entities_with_llm() tenta usar LLM NLU
   ├─ ✅ Sucesso → Retorna entities com/sem SKU
   │  ├─ Se TEM SKU → Rota para stock_check ✅
   │  └─ Se NÃO TEM SKU mas tem product_name → Resolve para SKU (linha 202-206) ✅
   │
   └─ ❌ Erro 401 → Cai em extract_entities_fallback()
      ├─ Fallback extrai: sku=84903501, intent=stock_check ✅
      └─ Retorna entities correto ✅
      
4. Routing baseado em entities["intent"]
   ├─ stock_check + sku → direct_query (consulta DB) ✅
   ├─ stock_check + NO sku → ?? 
   └─ unknown → clarification (mensagem genérica) ❌
```

### Problema Identificado

O LLM NLU pode estar:
1. **Retornando com sucesso** mas com `entities["intent"] = "unknown"`
2. **Extraindo product_name** mas **NÃO resolvendo para SKU** (linha 202-206)
3. **Não extraindo product_name** corretamente

---

## 🧪 LOGS DE DEBUG ADICIONADOS

### Arquivo: `app/services/chat_service.py`
```python
# Linha 72-73
print(f"🔍 DEBUG - Entities extraídas: {entities}")

# Linha 80-81  
print(f"🔍 DEBUG - Routing: {routing}")
```

### Arquivo: `app/agents/conversational_agent.py`
```python
# Linha 411-412
print(f"🔍 DEBUG - generate_clarification_message called with entities: {entities}")
```

---

## 🚀 PRÓXIMOS PASSOS

### 1. Aguardar Rebuild Completo
```bash
# Comando em execução:
docker-compose down
docker-compose build api
docker-compose up -d
```

### 2. Testar Novamente com Logs
```bash
# Enviar a mesma pergunta no chat
# Monitorar logs em tempo real
docker-compose logs -f api | grep "DEBUG"
```

### 3. Análise dos Logs

**O que procurar:**

```bash
# Entities extraídas
🔍 DEBUG - Entities extraídas: {
  "sku": "84903501",  # ← Deve ter SKU aqui!
  "intent": "stock_check",  # ← Deve ser stock_check!
  "product_name": "a vantagem de ganhar sem preocupação",
  "confidence": "medium"
}

# Routing
🔍 DEBUG - Routing: {
  "agent": "direct_query",  # ← Deve ser direct_query!
  "reason": "Consulta direta ao banco de dados",
  "async": False
}
```

**Se aparecer:**
```bash
🔍 DEBUG - Entities extraídas: {
  "sku": None,  # ← PROBLEMA!
  "intent": "unknown",  # ← PROBLEMA!
  "product_name": None,  # ← PROBLEMA!
}

🔍 DEBUG - Routing: {
  "agent": "clarification",  # ← Por isso retorna mensagem genérica!
}
```

---

## 🔧 POSSÍVEIS CORREÇÕES

### Cenário 1: LLM NLU Não Extrai product_name

**Causa:** LLM está retornando intent mas não product_name.

**Solução:**
```python
# app/agents/conversational_agent.py, linha ~217
# Adicionar fallback DENTRO do try (antes da exception)

if not result.get("product_name"):
    # Tenta extrair com regex mesmo dentro do LLM flow
    product_name_patterns = [
        r"produto[:\s]+(.+?)(?:\?|$)",
        r"estoque\s+(?:do|da|de)?\s*(?:meu\s+)?produto[:\s]+(.+?)(?:\?|$)",
    ]
    for pattern in product_name_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            result["product_name"] = match.group(1).strip()
            break
```

---

### Cenário 2: Resolução de Nome Não Funciona

**Causa:** `resolve_product_name_to_sku()` não encontra (case-sensitive? encoding?).

**Solução:**
```python
# app/agents/conversational_agent.py
# Melhorar resolve_product_name_to_sku com mais tolerância

def resolve_product_name_to_sku(session: Session, product_name: str) -> Optional[str]:
    if not product_name or not product_name.strip():
        return None
    
    product_name_clean = product_name.strip().lower()
    
    # Remove acentos
    import unicodedata
    product_name_normalized = unicodedata.normalize('NFKD', product_name_clean)
    product_name_normalized = product_name_normalized.encode('ASCII', 'ignore').decode('ASCII')
    
    # Busca com LIKE mais permissiva
    from sqlmodel import select, func, or_
    
    produto = session.exec(
        select(Produto).where(
            or_(
                func.lower(Produto.nome) == product_name_clean,
                func.lower(Produto.nome).contains(product_name_clean),
                func.lower(Produto.nome).like(f"%{product_name_clean}%")
            )
        )
    ).first()
    
    return produto.sku if produto else None
```

---

### Cenário 3: Intent Classificado como "unknown"

**Causa:** LLM não detecta "estoque" como intent stock_check.

**Solução:**
```python
# app/agents/conversational_agent.py, linha ~211
# Adicionar fallback de intent

if result.get("intent") == "general_inquiry" or result.get("intent") == "unknown":
    # Fallback de intent baseado em palavras-chave
    message_lower = message.lower()
    if any(word in message_lower for word in ["estoque", "quantidade", "disponível", "tem"]):
        result["intent"] = "stock_check"
```

---

## 📊 CHECKLIST DE DIAGNÓSTICO

- [x] ✅ Produto existe no banco
- [x] ✅ Regex funciona
- [x] ✅ Fallback funciona
- [x] ✅ Código atualizado no container
- [ ] 🟡 Logs de debug adicionados (aguardando rebuild)
- [ ] 🟡 Teste com logs (aguardando)
- [ ] ⏳ Identificar ponto exato da falha
- [ ] ⏳ Aplicar correção específica

---

## 🎯 TESTE MANUAL DIRETO

Enquanto aguarda rebuild, teste direto no container:

```bash
docker-compose exec -T api python3 -c "
from app.core.database import engine
from app.services.chat_service import process_user_message
from sqlmodel import Session

message = 'Qual o estoque do meu produto: A vantagem de ganhar sem preocupação'
session_id = 999

with Session(engine) as session:
    print('🧪 Processando mensagem:', message)
    print()
    
    try:
        response = process_user_message(session, session_id, message)
        print('✅ Resposta:', response.content)
    except Exception as e:
        print('❌ Erro:', e)
        import traceback
        traceback.print_exc()
"
```

---

## 📚 ARQUIVOS MODIFICADOS (Debug)

1. **app/services/chat_service.py**
   - Linha 72-73: Log entities extraídas
   - Linha 80-81: Log routing

2. **app/agents/conversational_agent.py**
   - Linha 411-412: Log em generate_clarification_message

---

## 🎉 CONCLUSÃO PRELIMINAR

**O que sabemos:**
- ✅ Produto existe
- ✅ Código de extração funciona
- ✅ Fallback funciona perfeitamente

**O que NÃO sabemos ainda:**
- ❓ Por que o fluxo normal não está funcionando?
- ❓ LLM está retornando o quê exatamente?
- ❓ Routing está recebendo qual intent?

**Próximo passo:** 
Aguardar rebuild e analisar logs com DEBUG ativado.

---

**Documento gerado:** 2025-10-09 21:15 BRT  
**Tipo:** Diagnóstico  
**Status:** 🟡 Aguardando rebuild e testes
