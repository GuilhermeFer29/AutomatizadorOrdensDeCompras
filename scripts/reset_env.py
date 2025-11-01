#!/usr/bin/env python3
"""
Reset Completo do Ambiente (Banco + Modelos)

Remove banco de dados e diretórios de modelos para fresh start.
"""

import sys
import os
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import engine
from app.models.models import SQLModel


def reset_database():
    """Reseta banco de dados via SQLModel."""
    print("🔄 Resetando banco de dados...")
    try:
        SQLModel.metadata.drop_all(engine)
        print("✅ Tabelas removidas")
        
        SQLModel.metadata.create_all(engine)
        print("✅ Tabelas recriadas")
        return True
    except Exception as e:
        print(f"❌ Erro ao resetar banco: {e}")
        return False


def remove_models():
    """Remove diretórios de modelos."""
    model_dirs = [
        PROJECT_ROOT / "model",
        PROJECT_ROOT / "models",
        Path("/app/model"),
        Path("/app/models"),
    ]
    
    removed = 0
    for model_dir in model_dirs:
        if model_dir.exists():
            try:
                shutil.rmtree(model_dir)
                print(f"✅ Removido: {model_dir}")
                removed += 1
            except Exception as e:
                print(f"⚠️  Erro ao remover {model_dir}: {e}")
    
    return removed


def docker_reset():
    """Reseta via Docker Compose."""
    print("\n🐳 Resetando via Docker Compose...")
    try:
        # Parar containers
        subprocess.run(["docker-compose", "down", "--remove-orphans"], 
                      cwd=PROJECT_ROOT, capture_output=True)
        print("✅ Containers parados")
        
        # Remover volumes
        subprocess.run(["docker", "volume", "prune", "-f"], 
                      capture_output=True)
        print("✅ Volumes removidos")
        
        # Subir novamente
        subprocess.run(["docker-compose", "up", "-d"], 
                      cwd=PROJECT_ROOT, capture_output=True)
        print("✅ Containers reiniciados")
        
        return True
    except Exception as e:
        print(f"⚠️  Erro ao resetar Docker: {e}")
        return False


def main():
    print("=" * 70)
    print("🔴 RESET COMPLETO DO AMBIENTE")
    print("=" * 70)
    print("\n⚠️  AVISO: Este script vai apagar:")
    print("  - Banco de dados")
    print("  - Diretórios de modelos")
    print()
    
    response = input("Tem certeza que quer continuar? (s/n): ")
    if response.lower() != "s":
        print("❌ Operação cancelada")
        return 1
    
    print()
    
    # Reset local
    db_ok = reset_database()
    models_removed = remove_models()
    
    # Tentar reset Docker se disponível
    docker_ok = False
    try:
        docker_ok = docker_reset()
    except:
        pass
    
    print()
    print("=" * 70)
    print("✅ RESET CONCLUÍDO!")
    print("=" * 70)
    print("\n⚠️  PRÓXIMOS PASSOS:")
    print("1. python scripts/create_tables.py")
    print("2. python scripts/seed_products.py")
    print("3. python scripts/generate_realistic_data.py --days 365")
    print("4. python scripts/validate_timeseries.py")
    print("5. python scripts/train_advanced_models.py --trials 10")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
