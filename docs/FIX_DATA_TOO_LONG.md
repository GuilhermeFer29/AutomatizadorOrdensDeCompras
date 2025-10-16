# Correção: Data too long for column 'content'

## 🐛 Problema

Erro ao salvar respostas longas do sistema híbrido:
```
mysql.connector.errors.DataError: 1406 (22001): Data too long for column 'content' at row 1
```

**Causa**: A coluna `content` da tabela `chat_messages` estava definida como `VARCHAR(255)` (limitado), mas o sistema híbrido pode gerar respostas com 30+ produtos (>2000 caracteres).

---

## ✅ Solução Aplicada

### 1. **Alteração no Modelo** (`app/models/models.py`)

**Antes:**
```python
content: str
metadata_json: Optional[str] = Field(default=None)
```

**Depois:**
```python
content: str = Field(sa_column=Column(Text))  # TEXT ilimitado
metadata_json: Optional[str] = Field(default=None, sa_column=Column(Text))
```

### 2. **Migração do Banco de Dados**

Execute o script de migração:
```bash
docker-compose exec api python scripts/migrate_chat_messages_to_text.py
```

Isso altera as colunas no MySQL:
- `content`: VARCHAR → TEXT
- `metadata_json`: VARCHAR → TEXT

### 3. **Limitação de Respostas** (`hybrid_query_service.py`)

Limitamos a formatação a **10 produtos** para evitar respostas excessivamente longas:

```python
limite = 10  # Máximo de produtos exibidos
if total > limite:
    response += f"\n_...e mais {total - limite} produto(s)._"
```

---

## 🚀 Passos para Aplicar

### 1. Reconstruir Container
```bash
docker-compose build api
```

### 2. Executar Migração
```bash
docker-compose up -d
docker-compose exec api python scripts/migrate_chat_messages_to_text.py
```

### 3. Testar
```bash
# No chat, pergunte:
"Quais produtos com estoque baixo?"
```

**Resultado esperado:**
```
⚠️ **Encontrei 30 produto(s) com estoque baixo:**

• **Produto 1** (SKU: ABC123)
  - Estoque: 5/10 unidades
  - Faltam: 5 unidades

• **Produto 2** (SKU: DEF456)
  ...

_...e mais 20 produto(s). Use filtros para refinar a busca._
```

---

## 📊 Tipos de Colunas MySQL

| Tipo | Tamanho Máximo | Uso |
|------|----------------|-----|
| VARCHAR(255) | 255 caracteres | ❌ Insuficiente para respostas longas |
| TEXT | 65,535 caracteres (~64KB) | ✅ Ideal para chat |
| MEDIUMTEXT | 16,777,215 caracteres (~16MB) | Para documentos grandes |
| LONGTEXT | 4,294,967,295 caracteres (~4GB) | Para dados massivos |

**Escolhemos TEXT**: Suporta até 64KB, mais que suficiente para respostas de chat.

---

## 🔍 Verificar Migração

```sql
-- Conectar ao MySQL
docker-compose exec db mysql -u root -p supply_chain_db

-- Verificar estrutura da tabela
DESCRIBE chat_messages;
```

**Resultado esperado:**
```
+---------------+----------+------+-----+---------+----------------+
| Field         | Type     | Null | Key | Default | Extra          |
+---------------+----------+------+-----+---------+----------------+
| id            | int      | NO   | PRI | NULL    | auto_increment |
| session_id    | int      | NO   | MUL | NULL    |                |
| sender        | varchar  | NO   |     | NULL    |                |
| content       | text     | NO   |     | NULL    |                | ✅
| metadata_json | text     | YES  |     | NULL    |                | ✅
| criado_em     | datetime | NO   |     | NULL    |                |
+---------------+----------+------+-----+---------+----------------+
```

---

## 🐛 Troubleshooting

### Erro: "Table doesn't exist"
```bash
# Recriar tabelas
docker-compose exec api python -c "from app.core.database import create_db_and_tables; create_db_and_tables()"
```

### Erro: "Column already modified"
Tudo bem! A migração já foi aplicada.

### Ainda dá erro de "Data too long"
Verifique se a migração foi executada:
```bash
docker-compose exec db mysql -u root -p supply_chain_db -e "DESCRIBE chat_messages;"
```

---

## 📚 Referências

- [SQLAlchemy Text Type](https://docs.sqlalchemy.org/en/20/core/type_basics.html#sqlalchemy.types.Text)
- [MySQL TEXT Types](https://dev.mysql.com/doc/refman/8.0/en/string-type-syntax.html)
- [SQLModel Column Override](https://sqlmodel.tiangolo.com/tutorial/create-db-and-table/#column-with-more-attributes)
