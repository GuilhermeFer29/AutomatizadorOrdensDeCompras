#!/usr/bin/env python3
"""
Script para testar conexão com Google Gemini API.

Verifica:
1. GOOGLE_API_KEY está configurada
2. google-genai está instalado
3. API está respondendo
4. Modelo gemini-2.5-pro está disponível
5. Embeddings text-embedding-004 funcionam
"""

import sys
import os
from pathlib import Path

# Adiciona app ao path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def test_api_key():
    """Testa se GOOGLE_API_KEY está configurada."""
    print("1️⃣  Testando GOOGLE_API_KEY...")
    
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("   ❌ GOOGLE_API_KEY não configurada!")
        print("   Configure no .env: GOOGLE_API_KEY=sua_chave_aqui")
        return False
    
    print(f"   ✅ API Key encontrada: {api_key[:20]}...")
    return True


def test_google_genai_import():
    """Testa se google-genai está instalado."""
    print("\n2️⃣  Testando instalação do google-genai...")
    
    try:
        from google import genai
        print("   ✅ google-genai importado com sucesso")
        return True
    except ImportError as e:
        print(f"   ❌ Erro ao importar: {e}")
        print("   Execute: pip install google-genai==0.4.0")
        return False


def test_gemini_connection():
    """Testa conexão com Gemini API."""
    print("\n3️⃣  Testando conexão com Gemini API...")
    
    try:
        from google import genai
        
        api_key = os.getenv("GOOGLE_API_KEY")
        client = genai.Client(api_key=api_key)
        
        # Testa chamada simples
        response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents="Diga apenas 'olá' em português."
        )
        
        result = response.text.strip().lower()
        print(f"   ✅ API respondeu: {result}")
        return True
        
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False


def test_embeddings():
    """Testa geração de embeddings."""
    print("\n4️⃣  Testando embeddings text-embedding-004...")
    
    try:
        from google import genai
        
        api_key = os.getenv("GOOGLE_API_KEY")
        client = genai.Client(api_key=api_key)
        
        # Gera embedding de teste
        response = client.models.embed_content(
            model="models/text-embedding-004",
            content="teste de embedding"
        )
        
        embedding = response.embeddings[0].values
        dimensions = len(embedding)
        
        print(f"   ✅ Embedding gerado: {dimensions} dimensões")
        
        if dimensions != 768:
            print(f"   ⚠️  Esperado 768 dimensões, recebido {dimensions}")
            return False
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False


def test_agno_gemini():
    """Testa integração Agno + Gemini."""
    print("\n5️⃣  Testando integração Agno + Gemini...")
    
    try:
        from agno.models.google import Gemini
        from agno.agent import Agent
        
        # Cria modelo
        model = Gemini(
            id="gemini-2.5-pro",
            api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.2
        )
        
        # Cria agente simples
        agent = Agent(
            model=model,
            instructions="Você é um assistente útil."
        )
        
        # Testa resposta
        response = agent.run("Diga apenas 'ok' em português.")
        result = str(response.content).strip().lower()
        
        print(f"   ✅ Agno + Gemini funcionando: {result}")
        return True
        
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False


def main():
    print("=" * 60)
    print("🧪 TESTE DE INTEGRAÇÃO GOOGLE GEMINI")
    print("=" * 60)
    print()
    
    results = []
    
    # Executa todos os testes
    results.append(("API Key", test_api_key()))
    
    if results[-1][1]:  # Se API key OK
        results.append(("google-genai", test_google_genai_import()))
        
        if results[-1][1]:  # Se import OK
            results.append(("Conexão API", test_gemini_connection()))
            results.append(("Embeddings", test_embeddings()))
            results.append(("Agno + Gemini", test_agno_gemini()))
    
    # Resumo
    print("\n" + "=" * 60)
    print("📊 RESUMO DOS TESTES")
    print("=" * 60)
    
    for test_name, success in results:
        status = "✅ PASSOU" if success else "❌ FALHOU"
        print(f"  {status}: {test_name}")
    
    all_passed = all(result[1] for result in results)
    
    print()
    if all_passed:
        print("🎉 TODOS OS TESTES PASSARAM!")
        print("✅ Sistema pronto para usar Gemini")
    else:
        print("❌ ALGUNS TESTES FALHARAM")
        print("⚠️  Verifique os erros acima")
        sys.exit(1)


if __name__ == "__main__":
    main()
