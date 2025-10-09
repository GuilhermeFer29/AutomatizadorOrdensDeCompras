#!/usr/bin/env python3
"""
Script de Validação das Correções da API Agno.

Execute este script para verificar se todas as correções foram aplicadas
corretamente e se o sistema está funcionando com a API moderna do Agno.

Uso:
    python test_agno_corrections.py
"""

import sys
import os

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_imports():
    """Teste 1: Verificar se todos os imports funcionam."""
    print("🧪 Teste 1: Verificando imports...")
    try:
        from app.agents import supply_chain_team
        from app.agents import conversational_agent
        from app.agents import tools
        from app.tasks import agent_tasks
        print("✅ Todos os imports funcionaram!\n")
        return True
    except Exception as e:
        print(f"❌ Erro nos imports: {e}\n")
        return False


def test_llm_configuration():
    """Teste 2: Verificar configuração do LLM."""
    print("🧪 Teste 2: Verificando configuração do LLM...")
    try:
        from app.agents.supply_chain_team import _get_llm_for_agno
        
        # Tenta criar o modelo
        llm = _get_llm_for_agno(temperature=0.2)
        
        # Verifica se tem os atributos corretos
        assert hasattr(llm, 'id'), "LLM deve ter atributo 'id'"
        assert hasattr(llm, 'api_key'), "LLM deve ter atributo 'api_key'"
        assert hasattr(llm, 'base_url'), "LLM deve ter atributo 'base_url'"
        
        print("✅ Configuração do LLM correta!")
        print(f"   - Modelo: {llm.id}")
        print(f"   - Base URL: {llm.base_url}")
        print(f"   - Temperature: {llm.temperature}\n")
        return True
    except Exception as e:
        print(f"❌ Erro na configuração do LLM: {e}\n")
        return False


def test_agent_creation():
    """Teste 3: Verificar criação de Agent com API moderna."""
    print("🧪 Teste 3: Verificando criação de Agent...")
    try:
        from agno.agent import Agent
        from app.agents.supply_chain_team import _get_llm_for_agno
        
        # Cria um agent de teste
        agent = Agent(
            description="Test Agent - Verificação de API",
            model=_get_llm_for_agno(temperature=0.2),
            instructions=["Você é um assistente de teste."],
            show_tool_calls=True,
            markdown=True,
        )
        
        # Verifica atributos
        assert hasattr(agent, 'description'), "Agent deve ter 'description'"
        assert hasattr(agent, 'model'), "Agent deve ter 'model'"
        assert hasattr(agent, 'instructions'), "Agent deve ter 'instructions'"
        
        print("✅ Agent criado com API moderna!")
        print(f"   - Description: {agent.description}")
        print(f"   - Show tool calls: {agent.show_tool_calls}")
        print(f"   - Markdown: {agent.markdown}\n")
        return True
    except Exception as e:
        print(f"❌ Erro na criação do Agent: {e}\n")
        return False


def test_team_creation():
    """Teste 4: Verificar criação de Team."""
    print("🧪 Teste 4: Verificando criação de Team...")
    try:
        from app.agents.supply_chain_team import create_supply_chain_team
        
        # Cria o team
        team = create_supply_chain_team()
        
        # Verifica atributos
        assert hasattr(team, 'agents'), "Team deve ter 'agents'"
        assert len(team.agents) == 4, "Team deve ter 4 agentes"
        assert hasattr(team, 'mode'), "Team deve ter 'mode'"
        assert team.mode == "coordinate", "Team deve estar em mode='coordinate'"
        
        print("✅ Team criado com sucesso!")
        print(f"   - Número de agentes: {len(team.agents)}")
        print(f"   - Modo: {team.mode}")
        print("   - Agentes:")
        for agent in team.agents:
            print(f"      • {agent.description}")
        print()
        return True
    except Exception as e:
        print(f"❌ Erro na criação do Team: {e}\n")
        return False


def test_toolkit():
    """Teste 5: Verificar SupplyChainToolkit."""
    print("🧪 Teste 5: Verificando SupplyChainToolkit...")
    try:
        from app.agents.tools import SupplyChainToolkit
        
        # Cria o toolkit
        toolkit = SupplyChainToolkit()
        
        # Verifica métodos
        assert hasattr(toolkit, 'lookup_product'), "Toolkit deve ter 'lookup_product'"
        assert hasattr(toolkit, 'load_demand_forecast'), "Toolkit deve ter 'load_demand_forecast'"
        assert hasattr(toolkit, 'scrape_latest_price'), "Toolkit deve ter 'scrape_latest_price'"
        assert hasattr(toolkit, 'compute_distance'), "Toolkit deve ter 'compute_distance'"
        assert hasattr(toolkit, 'wikipedia_search'), "Toolkit deve ter 'wikipedia_search'"
        
        print("✅ SupplyChainToolkit criado com sucesso!")
        print(f"   - Ferramentas disponíveis: {len([m for m in dir(toolkit) if not m.startswith('_')])}")
        print()
        return True
    except Exception as e:
        print(f"❌ Erro no SupplyChainToolkit: {e}\n")
        return False


def test_nlu_agent():
    """Teste 6: Verificar Agent NLU com response_model."""
    print("🧪 Teste 6: Verificando Agent NLU...")
    try:
        from agno.agent import Agent
        from app.agents.conversational_agent import _get_llm_for_agno
        
        # Cria agent NLU de teste
        agent = Agent(
            description="Test NLU Agent",
            model=_get_llm_for_agno(temperature=0.2),
            instructions=["Você extrai entidades de mensagens."],
            response_model=dict,
            show_tool_calls=True,
            markdown=False,
        )
        
        # Verifica atributos
        assert hasattr(agent, 'response_model'), "Agent deve ter 'response_model'"
        assert agent.response_model == dict, "response_model deve ser dict"
        
        print("✅ Agent NLU configurado corretamente!")
        print(f"   - Response model: {agent.response_model}")
        print(f"   - Markdown: {agent.markdown}")
        print()
        return True
    except Exception as e:
        print(f"❌ Erro no Agent NLU: {e}\n")
        return False


def test_function_signatures():
    """Teste 7: Verificar assinaturas das funções principais."""
    print("🧪 Teste 7: Verificando assinaturas de funções...")
    try:
        from app.agents import supply_chain_team
        import inspect
        
        # Verifica run_supply_chain_analysis
        assert hasattr(supply_chain_team, 'run_supply_chain_analysis'), \
            "Deve ter função 'run_supply_chain_analysis'"
        
        sig = inspect.signature(supply_chain_team.run_supply_chain_analysis)
        params = list(sig.parameters.keys())
        assert 'inquiry' in params, "Deve ter parâmetro 'inquiry'"
        
        # Verifica execute_supply_chain_team (legado)
        assert hasattr(supply_chain_team, 'execute_supply_chain_team'), \
            "Deve ter função 'execute_supply_chain_team' (compatibilidade)"
        
        print("✅ Assinaturas de funções corretas!")
        print(f"   - run_supply_chain_analysis: {params}")
        print()
        return True
    except Exception as e:
        print(f"❌ Erro nas assinaturas: {e}\n")
        return False


def main():
    """Executa todos os testes."""
    print("=" * 70)
    print("🔍 VALIDAÇÃO DAS CORREÇÕES DA API AGNO")
    print("=" * 70)
    print()
    
    tests = [
        test_imports,
        test_llm_configuration,
        test_agent_creation,
        test_team_creation,
        test_toolkit,
        test_nlu_agent,
        test_function_signatures,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Erro inesperado: {e}\n")
            results.append(False)
    
    # Resumo
    print("=" * 70)
    print("📊 RESUMO DOS TESTES")
    print("=" * 70)
    passed = sum(results)
    total = len(results)
    percentage = (passed / total) * 100
    
    print(f"✅ Testes passados: {passed}/{total} ({percentage:.0f}%)")
    
    if passed == total:
        print("\n🎉 TODAS AS CORREÇÕES FORAM APLICADAS CORRETAMENTE!")
        print("   O sistema está usando a API moderna do Agno.")
        return 0
    else:
        print(f"\n⚠️  Alguns testes falharam ({total - passed}).")
        print("   Revise os erros acima e corrija os problemas.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
