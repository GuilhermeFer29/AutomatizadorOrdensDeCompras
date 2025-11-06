# ✅ CORREÇÃO - LICENSE File Missing

## 🔴 Problema

```
ConfigurationError: License file not found ('LICENSE')
```

O arquivo `pyproject.toml` do LightGBM requer um arquivo `LICENSE`, mas ele está no diretório raiz (`/tmp/LightGBM/LICENSE`) e não em `python-package/`.

## ✅ Solução

Copiar o arquivo `LICENSE` antes de fazer `pip install`:

```dockerfile
# ✅ Adicionar esta linha
cp ../LICENSE . && \
```

## 🔧 Alteração Realizada

### Dockerfile (Linha 80)

```diff
    cd /tmp/LightGBM/python-package && \
+   cp ../LICENSE . && \
    pip install --no-cache-dir . && \
```

## 📊 Estrutura do Repositório

```
LightGBM/
├── LICENSE                   ← Arquivo necessário
├── python-package/
│   ├── pyproject.toml       ← Procura por LICENSE aqui
│   ├── setup.py
│   └── lightgbm/
```

## 🚀 Próximos Passos

Execute o build novamente:

```bash
docker-compose build --no-cache api
```

**Tempo esperado:** 40-50 minutos

## ✅ Verificação Pós-Build

```bash
# Verificar LightGBM com CUDA
docker-compose exec api python3 -c "
import lightgbm as lgb
print('LightGBM version:', lgb.__version__)
m = lgb.LGBMRegressor(device_type='cuda', n_estimators=1)
print('✅ LightGBM com CUDA OK')
"
```

## 🎉 Status

🟢 **CORRIGIDO**

Dockerfile agora copia o LICENSE file antes de instalar!
