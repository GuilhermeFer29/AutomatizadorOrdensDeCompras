"""
Configuração Centralizada do LLM Gemini.

Este módulo fornece uma função única para configurar e retornar instâncias
do modelo Gemini, garantindo consistência em todo o projeto e facilitando
manutenção futura.

Autor: Sistema de Automação de Compras
Data: 2025-10-10
"""

import os
from typing import Optional
from agno.models.google import Gemini


def get_gemini_llm(
    temperature: float = 0.3,
    model_id: str = "models/gemini-2.5-flash-latest"
) -> Gemini:
    """
    Configura e retorna uma instância do modelo Google Gemini.
    
    Esta é a ÚNICA função que deve ser usada para criar instâncias do LLM
    em todo o projeto. Isso garante:
    - Configuração consistente em todos os agentes
    - Carregamento centralizado da API key
    - Fácil manutenção e atualização de versões
    - Validação adequada de variáveis de ambiente
    
    Args:
        temperature: Controla a aleatoriedade das respostas (0.0 = determinístico, 1.0 = criativo).
                    Padrão: 0.3 (bom para tarefas analíticas)
        model_id: ID do modelo Gemini a ser usado.
                 Padrão: "models/gemini-2.5-flash-latest" (mais recente e estável)
                 Alternativas:
                 - "models/gemini-2.5-flash-latest" (mais rápido, menos preciso)
                 - "models/gemini-2.5-pro-latest" (versão anterior)
    
    Returns:
        Gemini: Instância configurada do modelo Gemini pronta para uso.
    
    Raises:
        ValueError: Se a variável de ambiente GOOGLE_API_KEY não estiver configurada.
    
    Example:
        ```python
        from app.agents.llm_config import get_gemini_llm
        from agno.agent import Agent
        
        # Obter modelo configurado
        llm = get_gemini_llm()
        
        # Usar em um agente
        agent = Agent(
            model=llm,
            instructions="Você é um assistente especializado."
        )
        ```
    
    Notas:
        - A API key deve ser definida no arquivo .env: GOOGLE_API_KEY=sua_chave_aqui
        - Obtenha sua chave em: https://aistudio.google.com/app/apikey
        - O modelo Gemini 2.5 Flash suporta:
          * Contexto de até 1M tokens
          * Multimodal (texto, imagem, áudio)
          * Function calling avançado
          * JSON mode nativo
    """
    # Carrega API key do ambiente
    api_key = os.getenv("GOOGLE_API_KEY")
    
    # Validação crítica: sem API key = sem funcionamento
    if not api_key:
        raise ValueError(
            "❌ ERRO CRÍTICO: A variável de ambiente 'GOOGLE_API_KEY' não está configurada.\n"
            "\n"
            "Por favor, adicione-a ao seu arquivo .env:\n"
            "  GOOGLE_API_KEY=sua_chave_aqui\n"
            "\n"
            "Obtenha sua chave gratuita em:\n"
            "  https://aistudio.google.com/app/apikey\n"
            "\n"
            "Após adicionar, reinicie a aplicação com:\n"
            "  docker-compose restart api worker\n"
        )
    
    # Log de configuração (útil para debug)
    masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
    print(f"🤖 Gemini LLM configurado: {model_id} (temp={temperature}, key={masked_key})")
    
    # Cria e retorna instância configurada
    return Gemini(
        id=model_id,
        api_key=api_key,
        temperature=temperature,
        # Configurações adicionais (podem ser expandidas conforme necessário)
        # max_tokens=None,  # Usa o máximo do modelo
        # top_p=0.95,       # Nucleus sampling
        # top_k=40,         # Top-k sampling
    )


def get_gemini_for_nlu() -> Gemini:
    """
    Retorna uma instância do Gemini otimizada para tarefas de NLU (Natural Language Understanding).
    
    Configuração especializada:
    - Temperature baixa (0.1) para respostas mais determinísticas
    - Ideal para extração de entidades e classificação de intenções
    
    Returns:
        Gemini: Instância otimizada para NLU.
    """
    return get_gemini_llm(temperature=0.1)


def get_gemini_for_creative() -> Gemini:
    """
    Retorna uma instância do Gemini otimizada para tarefas criativas.
    
    Configuração especializada:
    - Temperature alta (0.7) para respostas mais variadas
    - Ideal para geração de relatórios e análises narrativas
    
    Returns:
        Gemini: Instância otimizada para criação de conteúdo.
    """
    return get_gemini_llm(temperature=0.7)


# Validação ao importar o módulo
if __name__ == "__main__":
    print("🧪 Testando configuração do Gemini LLM...")
    
    try:
        llm = get_gemini_llm()
        print(f"✅ Sucesso! Modelo configurado: {llm.id}")
        print(f"   Temperature: {llm.temperature}")
        print(f"   API Key: {'✓ Configurada' if llm.api_key else '✗ Ausente'}")
    except ValueError as e:
        print(f"❌ Erro: {e}")
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
