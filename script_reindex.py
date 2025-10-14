#!/usr/bin/env python
"""
Script de Reindexação do Catálogo de Produtos

Indexa todos os produtos do banco de dados no ChromaDB usando a nova
arquitetura LangChain + Google AI.

IMPORTANTE: Execute este script SEMPRE que:
1. Atualizar a estrutura do RAG
2. Mudar o modelo de embeddings
3. Adicionar novos produtos ao catálogo
4. Após deletar o diretório data/chroma

Execute: python script_reindex.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

# Carrega variáveis de ambiente
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Variáveis de ambiente carregadas do .env\n")
except ImportError:
    print("⚠️ python-dotenv não instalado - usando env do sistema\n")


def print_banner():
    """Exibe banner do script."""
    print("\n" + "=" * 80)
    print("  REINDEXAÇÃO DO CATÁLOGO DE PRODUTOS")
    print("  LangChain + Google AI Embeddings (text-embedding-004)")
    print("=" * 80 + "\n")


def validate_environment():
    """Valida que o ambiente está configurado corretamente."""
    print("🔍 Validando ambiente...\n")
    
    # 1. Verifica API Key
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ ERRO: GOOGLE_API_KEY não configurada!")
        print("\nConfigure no arquivo .env:")
        print("  GOOGLE_API_KEY=sua_chave_aqui")
        print("\nObtenha em: https://aistudio.google.com/app/apikey")
        return False
    
    masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
    print(f"✅ GOOGLE_API_KEY: {masked_key}")
    
    # 2. Verifica imports
    try:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        from app.services.rag_service import index_product_catalog
        from app.core.database import engine
        print("✅ Dependências importadas")
    except ImportError as e:
        print(f"❌ ERRO ao importar dependências: {e}")
        print("\nExecute: pip install -r requirements.txt")
        return False
    
    # 3. Verifica conexão com banco
    try:
        from sqlmodel import Session, select
        from app.models.models import Produto
        
        with Session(engine) as session:
            count = session.exec(select(Produto)).all()
            product_count = len(count)
        
        if product_count == 0:
            print("⚠️ AVISO: Nenhum produto encontrado no banco de dados")
            print("   A reindexação será vazia. Adicione produtos primeiro.")
            return True  # Não é erro fatal, mas avisa
        
        print(f"✅ Banco de dados: {product_count} produtos encontrados")
        
    except Exception as e:
        print(f"❌ ERRO ao conectar com banco: {e}")
        print("\nVerifique:")
        print("  1. Banco de dados está rodando?")
        print("  2. Credenciais no .env estão corretas?")
        return False
    
    print()
    return True


def check_chroma_directory():
    """Verifica o estado do diretório ChromaDB."""
    chroma_dir = Path(__file__).parent / "data" / "chroma"
    
    print("📁 Verificando diretório ChromaDB...\n")
    
    if chroma_dir.exists():
        # Conta arquivos
        file_count = sum(1 for _ in chroma_dir.rglob("*") if _.is_file())
        print(f"⚠️ Diretório ChromaDB existe: {chroma_dir}")
        print(f"   Contém {file_count} arquivos")
        
        # Pergunta se quer deletar
        print("\n🔄 Recomendação: Delete o diretório antigo para evitar conflitos")
        print("   (A reindexação criará uma nova versão)")
        
        response = input("\n❓ Deseja deletar o ChromaDB existente? [s/N]: ").strip().lower()
        
        if response in ['s', 'sim', 'y', 'yes']:
            try:
                import shutil
                shutil.rmtree(chroma_dir)
                print(f"✅ Diretório deletado: {chroma_dir}")
            except Exception as e:
                print(f"❌ Erro ao deletar diretório: {e}")
                print("   Delete manualmente: rm -rf data/chroma")
                return False
        else:
            print("⏭️ Mantendo diretório existente (pode causar conflitos)")
    else:
        print(f"✅ Diretório ChromaDB será criado: {chroma_dir}")
    
    print()
    return True


def perform_indexing():
    """Executa a reindexação do catálogo."""
    print("🚀 Iniciando reindexação...\n")
    
    try:
        from app.core.database import engine
        from app.services.rag_service import index_product_catalog
        from sqlmodel import Session
        
        start_time = datetime.now()
        
        with Session(engine) as session:
            # Chama a função de indexação do RAG service
            index_product_catalog(session)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print(f"\n✅ Reindexação concluída em {duration:.2f} segundos!")
        return True
        
    except Exception as e:
        print(f"\n❌ ERRO durante reindexação: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_indexing():
    """Verifica se a indexação foi bem-sucedida."""
    print("\n🔍 Verificando indexação...\n")
    
    try:
        from app.services.rag_service import query_product_catalog_with_google_rag
        
        # Teste simples de busca
        test_query = "Me mostre os produtos disponíveis"
        print(f"📝 Query de teste: '{test_query}'")
        
        response = query_product_catalog_with_google_rag(test_query)
        
        if response and not response.startswith("❌"):
            print("\n✅ Teste de busca RAG: PASSOU")
            print(f"\n📋 Resposta de exemplo ({len(response)} caracteres):")
            print("-" * 80)
            # Mostra apenas os primeiros 300 caracteres
            preview = response[:300] + "..." if len(response) > 300 else response
            print(preview)
            print("-" * 80)
            return True
        else:
            print("\n⚠️ Teste de busca RAG retornou erro")
            print(f"Resposta: {response}")
            return False
            
    except Exception as e:
        print(f"\n❌ ERRO ao verificar indexação: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Função principal."""
    print_banner()
    
    # 1. Validação do ambiente
    if not validate_environment():
        print("\n❌ Validação falhou. Corrija os erros acima e tente novamente.\n")
        return 1
    
    # 2. Verificação do ChromaDB
    if not check_chroma_directory():
        print("\n❌ Problema com diretório ChromaDB.\n")
        return 1
    
    # 3. Confirmação
    print("─" * 80)
    print("\n🎯 PRONTO PARA REINDEXAR\n")
    print("   Isso irá:")
    print("   • Carregar todos os produtos do banco de dados")
    print("   • Gerar embeddings usando Google text-embedding-004")
    print("   • Armazenar no ChromaDB para busca semântica")
    print()
    
    response = input("❓ Continuar com a reindexação? [S/n]: ").strip().lower()
    
    if response in ['n', 'no', 'não', 'nao']:
        print("\n⏹️ Reindexação cancelada pelo usuário.\n")
        return 0
    
    print()
    print("─" * 80)
    
    # 4. Executa reindexação
    if not perform_indexing():
        print("\n❌ Reindexação falhou.\n")
        return 1
    
    # 5. Verifica resultado
    if not verify_indexing():
        print("\n⚠️ Reindexação concluída mas a verificação falhou.")
        print("   O catálogo pode estar vazio ou com problemas.\n")
        return 1
    
    # Sucesso!
    print("\n" + "=" * 80)
    print("  ✅ REINDEXAÇÃO CONCLUÍDA COM SUCESSO!")
    print("=" * 80)
    
    print("\n📝 Próximos passos:")
    print("   1. Execute: python test_hybrid_architecture.py")
    print("   2. Ou teste interativamente: python interactive_chat.py")
    print("   3. Consulte: GUIA_VALIDACAO_ASSISTENTE_CONVERSACIONAL.md")
    print()
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️ Reindexação interrompida pelo usuário.\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Erro fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
