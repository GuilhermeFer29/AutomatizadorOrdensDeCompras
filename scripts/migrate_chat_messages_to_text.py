"""
Migração: Altera colunas content e metadata_json de VARCHAR para TEXT
para suportar respostas longas do sistema híbrido.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import os

load_dotenv()

def migrate():
    """Executa migração das colunas."""
    
    # Conecta ao banco
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL não encontrada no .env")
        return
    
    engine = create_engine(db_url)
    
    print("🔄 Iniciando migração de chat_messages...")
    
    with engine.connect() as conn:
        try:
            # Altera coluna content para TEXT
            print("📝 Alterando coluna 'content' para TEXT...")
            conn.execute(text("""
                ALTER TABLE chat_messages 
                MODIFY COLUMN content TEXT NOT NULL
            """))
            
            # Altera coluna metadata_json para TEXT
            print("📝 Alterando coluna 'metadata_json' para TEXT...")
            conn.execute(text("""
                ALTER TABLE chat_messages 
                MODIFY COLUMN metadata_json TEXT NULL
            """))
            
            conn.commit()
            print("✅ Migração concluída com sucesso!")
            
        except Exception as e:
            print(f"❌ Erro na migração: {e}")
            conn.rollback()
            raise

if __name__ == "__main__":
    migrate()
