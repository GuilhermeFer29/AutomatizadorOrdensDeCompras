#!/usr/bin/env python3
"""
Script para verificar configuração e uso de quota do Gemini API.

Uso:
    python scripts/check_gemini_quota.py
"""

import os
import sys
from pathlib import Path

# Adiciona o diretório raiz ao path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()


def check_api_key():
    """Verifica se a API key está configurada."""
    api_key = os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        print("❌ GOOGLE_API_KEY não configurada no .env")
        return False
    
    # Mascara a chave para exibição
    masked = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
    print(f"✅ GOOGLE_API_KEY configurada: {masked}")
    return True


def check_model_config():
    """Verifica qual modelo será usado."""
    use_pro = os.getenv("GEMINI_USE_PRO", "false").lower() == "true"
    
    if use_pro:
        print("⚠️  GEMINI_USE_PRO=true")
        print("    Modelo: gemini-2.5-pro")
        print("    Quota Free Tier: 50 requisições/dia")
        print("    ⚠️  ATENÇÃO: Quota muito limitada! Use apenas com plano pago.")
    else:
        print("✅ GEMINI_USE_PRO=false (padrão)")
        print("    Modelo: gemini-2.5-flash")
        print("    Quota Free Tier: 1500 requisições/dia")
        print("    ✅ Recomendado para desenvolvimento e testes")
    
    return not use_pro  # Retorna True se está usando Flash (seguro)


def estimate_daily_usage():
    """Estima uso diário baseado na arquitetura do sistema."""
    print("\n📊 ESTIMATIVA DE USO DIÁRIO:")
    print("=" * 60)
    
    # Configuração do sistema
    agents_per_analysis = 4  # AnalistaDemanda, Pesquisador, Logistica, Gerente
    team_coordinator = 1     # Team faz coordenação
    conversational = 1       # ConversationalAgent
    
    print(f"Por análise completa de compra:")
    print(f"  - Agentes especialistas (Flash): {agents_per_analysis} chamadas")
    print(f"  - Gerente de Compras (Pro/Flash): {team_coordinator} chamada")
    print(f"  - Team coordenador (Pro/Flash): {team_coordinator} chamada")
    print(f"  - ConversationalAgent (Pro/Flash): {conversational} chamada")
    print(f"  Total por análise: ~{agents_per_analysis + team_coordinator * 2 + conversational} chamadas")
    
    print(f"\nCom configuração atual (Flash para todos):")
    
    scenarios = [
        (10, "Desenvolvimento/Testes"),
        (50, "Uso moderado"),
        (100, "Uso intenso"),
        (200, "Produção alta demanda"),
    ]
    
    for analyses, scenario in scenarios:
        total_calls = analyses * (agents_per_analysis + team_coordinator * 2 + conversational)
        flash_quota = 1500
        percentage = (total_calls / flash_quota) * 100
        
        status = "✅" if percentage < 80 else "⚠️" if percentage < 100 else "❌"
        print(f"  {status} {scenario:25s}: {analyses:3d} análises = {total_calls:4d} chamadas ({percentage:5.1f}% quota Flash)")


def check_rate_limits():
    """Mostra informações sobre rate limits."""
    print("\n⏱️  RATE LIMITS (FREE TIER):")
    print("=" * 60)
    
    print("Gemini 2.5 Flash:")
    print("  - RPM (requests/min): 15")
    print("  - RPD (requests/dia): 1500")
    print("  - TPM (tokens/min): 1M")
    print("  - Custo: Grátis")
    
    print("\nGemini 2.5 Pro:")
    print("  - RPM (requests/min): 2")
    print("  - RPD (requests/dia): 50")
    print("  - TPM (tokens/min): 32K")
    print("  - Custo: Grátis")
    
    print("\n💰 PLANO PAGO (Pay-as-you-go):")
    print("  - Flash: sem limite de RPD, $0.075/1M tokens")
    print("  - Pro: sem limite de RPD, $1.25/1M tokens")


def show_recommendations():
    """Mostra recomendações baseadas na configuração."""
    print("\n💡 RECOMENDAÇÕES:")
    print("=" * 60)
    
    use_pro = os.getenv("GEMINI_USE_PRO", "false").lower() == "true"
    
    if use_pro:
        print("⚠️  Você está usando Pro com free tier!")
        print("\n   AÇÕES RECOMENDADAS:")
        print("   1. Desabilite Pro: remova GEMINI_USE_PRO do .env")
        print("   2. OU faça upgrade para plano pago")
        print("   3. Reinicie: docker compose restart api")
        print("\n   Flash é suficiente para 95% dos casos e 30x mais quota.")
    else:
        print("✅ Configuração otimizada!")
        print("\n   Você está usando Flash que:")
        print("   - Tem quota 30x maior que Pro (1500 vs 50 req/dia)")
        print("   - É 2-3x mais rápido")
        print("   - É grátis no free tier")
        print("   - Tem qualidade excelente para seu caso de uso")
        print("\n   Para upgrade futuro (opcional):")
        print("   - Habilite faturamento em: https://aistudio.google.com/")
        print("   - Defina GEMINI_USE_PRO=true no .env")
        print("   - Custo estimado: ~$5-10/mês para uso moderado")


def main():
    """Função principal."""
    print("=" * 60)
    print("🔍 VERIFICAÇÃO DE CONFIGURAÇÃO GEMINI API")
    print("=" * 60)
    print()
    
    # Verifica API key
    if not check_api_key():
        print("\n❌ Configure GOOGLE_API_KEY no .env antes de continuar")
        print("   Obtenha em: https://aistudio.google.com/app/apikey")
        return 1
    
    print()
    
    # Verifica configuração de modelo
    is_safe = check_model_config()
    
    # Estimativas
    estimate_daily_usage()
    
    # Rate limits
    check_rate_limits()
    
    # Recomendações
    show_recommendations()
    
    print("\n" + "=" * 60)
    
    if is_safe:
        print("✅ Sistema configurado corretamente para evitar quota exceeded")
    else:
        print("⚠️  ATENÇÃO: Configuração pode levar a quota exceeded")
    
    print("=" * 60)
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
