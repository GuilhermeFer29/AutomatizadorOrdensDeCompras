"""
Gera fornecedores sintéticos e ofertas de produtos para simulação de mercado.

Este script cria:
1. Fornecedores fictícios com diferentes características
2. Ofertas de produtos com variação de preços
3. Simula um mercado competitivo para o agente pesquisador
"""

import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlmodel import Session, select

from app.core.database import engine
from app.models.models import Fornecedor, OfertaProduto, Produto

# Lista de nomes de fornecedores fictícios
FORNECEDORES_FICTICIOS = [
    "Distribuidora Nacional de Materiais Ltda",
    "Mega Atacado Industrial S.A.",
    "Fornecimentos Rápidos Express",
    "Central de Suprimentos Premium",
    "Atacadista Econômico do Brasil",
    "Distribuidora Delta Prime",
    "Suprimentos Alfa & Omega",
    "Comercial Beta Materiais",
    "Indústria & Comércio Gama",
    "Fornecedor Estrela Azul",
]


def generate_suppliers(session: Session, num_suppliers: int = 8) -> list[Fornecedor]:
    """
    Gera fornecedores sintéticos com características variadas.
    
    Args:
        session: Sessão do banco de dados
        num_suppliers: Número de fornecedores a criar
    
    Returns:
        Lista de fornecedores criados
    """
    fornecedores = []
    
    # Verificar se já existem fornecedores
    existing = session.exec(select(Fornecedor)).all()
    if existing:
        print(f"✅ {len(existing)} fornecedores já existem no banco. Pulando criação.")
        return existing
    
    print(f"🏭 Criando {num_suppliers} fornecedores sintéticos...")
    
    for i in range(num_suppliers):
        # Características aleatórias mas realistas
        confiabilidade = round(random.uniform(0.75, 0.98), 2)  # 75% a 98%
        prazo_entrega = random.choice([2, 3, 5, 7, 10, 14])  # Prazos comuns
        
        fornecedor = Fornecedor(
            nome=FORNECEDORES_FICTICIOS[i],
            confiabilidade=confiabilidade,
            prazo_entrega_dias=prazo_entrega,
            cep=f"{random.randint(10000, 99999):05d}-{random.randint(0, 999):03d}",
            latitude=round(random.uniform(-30, -10), 6),  # Latitude Brasil
            longitude=round(random.uniform(-55, -35), 6),  # Longitude Brasil
        )
        
        session.add(fornecedor)
        fornecedores.append(fornecedor)
        
        print(f"  ✓ {fornecedor.nome} (Confiabilidade: {confiabilidade*100:.0f}%, Prazo: {prazo_entrega}d)")
    
    session.commit()
    
    # Refresh para obter IDs
    for f in fornecedores:
        session.refresh(f)
    
    print(f"✅ {len(fornecedores)} fornecedores criados com sucesso!\n")
    
    return fornecedores


def generate_product_offers(
    session: Session,
    fornecedores: list[Fornecedor],
    coverage_percent: float = 0.6
) -> int:
    """
    Gera ofertas de produtos por fornecedores.
    
    Args:
        session: Sessão do banco de dados
        fornecedores: Lista de fornecedores
        coverage_percent: Percentual de produtos que terão ofertas (0.6 = 60%)
    
    Returns:
        Número de ofertas criadas
    """
    print(f"💰 Gerando ofertas de produtos...")
    
    # Buscar todos os produtos
    produtos = session.exec(select(Produto)).all()
    total_produtos = len(produtos)
    
    if not produtos:
        print("❌ Nenhum produto encontrado no banco. Execute o setup primeiro.")
        return 0
    
    # Selecionar subset de produtos que terão ofertas
    num_produtos_com_ofertas = int(total_produtos * coverage_percent)
    produtos_selecionados = random.sample(list(produtos), num_produtos_com_ofertas)
    
    ofertas_criadas = 0
    
    for produto in produtos_selecionados:
        # Buscar preço médio recente do produto
        preco_base = random.uniform(10, 500)  # Fallback
        
        # Cada produto terá ofertas de 2-5 fornecedores
        num_fornecedores_por_produto = random.randint(2, min(5, len(fornecedores)))
        fornecedores_selecionados = random.sample(fornecedores, num_fornecedores_por_produto)
        
        for fornecedor in fornecedores_selecionados:
            # Variação de preço: ±15% do preço base
            variacao = random.uniform(-0.15, 0.15)
            preco_ofertado = preco_base * (1 + variacao)
            preco_ofertado = max(preco_ofertado, 1.0)  # Mínimo R$ 1.00
            
            # Estoque disponível
            estoque = random.choice([50, 100, 200, 500, 1000])
            
            # Validade da oferta (30-90 dias)
            dias_validade = random.randint(30, 90)
            validade = datetime.now(timezone.utc) + timedelta(days=dias_validade)
            
            oferta = OfertaProduto(
                produto_id=produto.id,
                fornecedor_id=fornecedor.id,
                preco_ofertado=Decimal(str(round(preco_ofertado, 2))),
                estoque_disponivel=estoque,
                validade_oferta=validade,
            )
            
            session.add(oferta)
            ofertas_criadas += 1
    
    session.commit()
    
    print(f"✅ {ofertas_criadas} ofertas criadas para {num_produtos_com_ofertas} produtos!")
    print(f"   Cobertura: {coverage_percent*100:.0f}% do catálogo\n")
    
    return ofertas_criadas


def main():
    """Executa a geração de fornecedores e ofertas."""
    print("=" * 70)
    print("🏭 GERADOR DE MERCADO SINTÉTICO - Fornecedores e Ofertas")
    print("=" * 70)
    print()
    
    with Session(engine) as session:
        # 1. Criar fornecedores
        fornecedores = generate_suppliers(session, num_suppliers=8)
        
        # 2. Criar ofertas de produtos
        ofertas = generate_product_offers(session, fornecedores, coverage_percent=0.6)
        
        print("=" * 70)
        print("✅ MERCADO SINTÉTICO CRIADO COM SUCESSO!")
        print("=" * 70)
        print(f"📊 Resumo:")
        print(f"   • {len(fornecedores)} fornecedores ativos")
        print(f"   • {ofertas} ofertas de produtos disponíveis")
        print(f"   • Média de {ofertas/len(fornecedores):.0f} ofertas por fornecedor")
        print()
        print("🎯 O sistema agora pode:")
        print("   - Comparar preços entre fornecedores")
        print("   - Analisar confiabilidade vs. preço")
        print("   - Otimizar prazos de entrega")
        print("   - Recomendar compras baseadas em múltiplos critérios")
        print()


if __name__ == "__main__":
    main()
