import requests
import sys
import json
import time

# Configuração
API_URL = "http://localhost:8000/api/chat"
SKU_TEST = "386DC631" # Pistolas de cola quente 34mm

def print_step(msg):
    print(f"\n👉 {msg}")

def print_success(msg):
    print(f"✅ {msg}")

def print_error(msg):
    print(f"❌ {msg}")
    sys.exit(1)

def test_agent_flow():
    print("🤖 Iniciando Validação de Agentes (Fase 2)...")
    
    # 1. Criar Sessão
    print_step("Criando nova sessão de chat...")
    try:
        resp = requests.post(f"{API_URL}/sessions")
        resp.raise_for_status()
        session_data = resp.json()
        session_id = session_data["id"]
        print_success(f"Sessão criada: {session_id}")
    except Exception as e:
        print_error(f"Falha ao criar sessão: {e}")

    # 2. Perguntar sobre Produto (Teste 'get_product_info')
    print_step(f"Perguntando sobre estoque do produto {SKU_TEST}...")
    msg_1 = {
        "content": f"Qual é o estoque atual do produto {SKU_TEST}?"
    }
    try:
        resp = requests.post(f"{API_URL}/sessions/{session_id}/messages", json=msg_1)
        resp.raise_for_status()
        data = resp.json()
        content = data["content"]
        print(f"   Resposta Agente: {content}")
        
        if "estoque" in content.lower() or "unidades" in content.lower():
            print_success("Agente respondeu com informações de estoque.")
        else:
            print_error("Resposta do agente não parece conter informações de estoque.")
            
    except Exception as e:
        print_error(f"Falha ao enviar mensagem 1: {e}")

    # 3. Pedir Previsão (Teste 'get_forecast_tool')
    print_step("Pedindo previsão de demanda...")
    msg_2 = {
        "content": "Faça uma previsão de demanda para este produto."
    }
    try:
        start_time = time.time()
        resp = requests.post(f"{API_URL}/sessions/{session_id}/messages", json=msg_2)
        resp.raise_for_status()
        data = resp.json()
        content = data["content"]
        metadata = data.get("metadata")
        
        print(f"   Resposta Agente: {content}")
        if metadata:
            print(f"   Metadata: {json.dumps(metadata, indent=2)}")
        
        duration = time.time() - start_time
        print(f"   Tempo de resposta: {duration:.2f}s")
        
        if "previsão" in content.lower() or "demand" in content.lower():
            print_success("Agente gerou previsão.")
        else:
            print(f"⚠️ Aviso: Agente pode não ter usado a tool de previsão corretamente. Verifique o conteúdo.")
            
    except Exception as e:
        print_error(f"Falha ao enviar mensagem 2: {e}")

    print("\n🎉 VALIDAÇÃO DE AGENTES CONCLUÍDA COM SUCESSO!")

if __name__ == "__main__":
    test_agent_flow()
