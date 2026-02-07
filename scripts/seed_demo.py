"""
Seed Demo Script - Industrial Supply Chain Automation.
Gera uma massa de dados realista para testes e demonstração.
"""

import sys
import os
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import List

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlmodel import Session, select, delete, SQLModel, create_engine
from app.models.models import (
    Produto, Fornecedor, OfertaProduto, PrecosHistoricos, 
    VendasHistoricas, OrdemDeCompra, AuditoriaDecisao, Agente
)

# Criar engine dedicado para o seed (evita conflitos)
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://app_user:app_password@db:3306/app_db")
seed_engine = create_engine(DATABASE_URL, pool_pre_ping=True)

def clear_db():
    print("🗑️ Resetando esquema do banco de dados (SaaS)...")
    SQLModel.metadata.drop_all(seed_engine)
    SQLModel.metadata.create_all(seed_engine)
    
    print("🏢 Criando Tenant padrão...")
    from app.models.models import Tenant
    with Session(seed_engine) as session:
        default_tenant = Tenant(
            nome="PMI Standard", 
            slug="standard", 
            plano="pro",
            ativo=True
        )
        session.add(default_tenant)
        session.commit()
        session.refresh(default_tenant)
        return default_tenant.id

def clear_data_only(session: Session):
    print("🧹 Limpando dados existentes...")
    session.exec(delete(AuditoriaDecisao))
    session.exec(delete(OrdemDeCompra))
    session.exec(delete(OfertaProduto))
    session.exec(delete(PrecosHistoricos))
    session.exec(delete(VendasHistoricas))
    session.exec(delete(Fornecedor))
    session.exec(delete(Produto))
    session.exec(delete(Agente))
    session.commit()

def seed_agentes(session: Session):
    print("🤖 Populando agentes...")
    agentes = [
        Agente(nome="Analisador de Demanda", descricao="Analisa histórico de vendas e prevê necessidade de estoque.", status="active"),
        Agente(nome="Otimizador de Compras", descricao="Compara fornecedores e recomenda a melhor opção de compra.", status="active"),
        Agente(nome="Auditores de Risco", descricao="Verifica saúde do fornecedor e prazos de entrega.", status="inactive")
    ]
    for a in agentes:
        session.add(a)
    session.commit()

def seed_demo():
    tenant_id = clear_db()
    
    print(f"🔑 Usando Tenant ID: {tenant_id}")
    
    with Session(seed_engine) as session:
        # Injetar tenant_id nos agentes
        print("🤖 Populando agentes...")
        agentes = [
            Agente(nome="Analisador de Demanda", descricao="Analisa histórico de vendas e prevê necessidade de estoque.", status="active", tenant_id=tenant_id),
            Agente(nome="Otimizador de Compras", descricao="Compara fornecedores e recomenda a melhor opção de compra.", status="active", tenant_id=tenant_id),
            Agente(nome="Auditores de Risco", descricao="Verifica saúde do fornecedor e prazos de entrega.", status="inactive", tenant_id=tenant_id)
        ]
        for a in agentes:
            session.add(a)
        session.commit()

        print("🏭 Criando fornecedores...")
        fornecedores = [
            Fornecedor(nome="Metalúrgica Central", cep="01001-000", confiabilidade=0.98, prazo_entrega_dias=3, tenant_id=tenant_id),
            Fornecedor(nome="Elétrica Industrial Ltda", cep="04578-000", confiabilidade=0.88, prazo_entrega_dias=5, tenant_id=tenant_id),
            Fornecedor(nome="Química do Brasil", cep="13083-000", confiabilidade=0.92, prazo_entrega_dias=10, tenant_id=tenant_id),
            Fornecedor(nome="Distribuidora Express", cep="80215-000", confiabilidade=0.75, prazo_entrega_dias=2, tenant_id=tenant_id),
            Fornecedor(nome="Importadora Técnica", cep="20020-000", confiabilidade=0.85, prazo_entrega_dias=30, tenant_id=tenant_id)
        ]
        for f in fornecedores:
            session.add(f)
        session.flush()

        print("📦 Criando produtos e categoria...")
        catalogo = [
            {"nome": "Parafuso Sextavado M12x50", "sku": "MEC-001", "cat": "Mecânica", "estoque": 500, "min": 200, "preco": 2.50},
            {"nome": "Rolamento Autocompensador", "sku": "MEC-002", "cat": "Mecânica", "estoque": 25, "min": 10, "preco": 145.00},
            {"nome": "Inversor de Frequência 10CV", "sku": "ELE-001", "cat": "Elétrica", "estoque": 8, "min": 5, "preco": 3200.00},
            {"nome": "Cabo Flexível 4mm (100m)", "sku": "ELE-002", "cat": "Elétrica", "estoque": 40, "min": 20, "preco": 280.00},
            {"nome": "Óleo Hidráulico ISO 68", "sku": "INS-001", "cat": "Insumos", "estoque": 200, "min": 100, "preco": 18.00},
            {"nome": "Luva Nitrílica G", "sku": "INS-002", "cat": "Insumos", "estoque": 150, "min": 100, "preco": 45.00},
            {"nome": "Furadeira de Bancada", "sku": "FER-001", "cat": "Ferramentas", "estoque": 3, "min": 2, "preco": 1850.00},
            {"nome": "Multímetro Digital Pro", "sku": "FER-002", "cat": "Ferramentas", "estoque": 12, "min": 10, "preco": 420.00},
            {"nome": "Válvula Solenóide 1/2", "sku": "MEC-003", "cat": "Mecânica", "estoque": 15, "min": 15, "preco": 290.00},
            {"nome": "Contatora 32A 220V", "sku": "ELE-003", "cat": "Elétrica", "estoque": 30, "min": 15, "preco": 120.00}
        ]

        produtos_criados = []
        for item in catalogo:
            p = Produto(
                nome=item["nome"],
                sku=item["sku"],
                categoria=item["cat"],
                estoque_atual=item["estoque"],
                estoque_minimo=item["min"],
                tenant_id=tenant_id
            )
            session.add(p)
            produtos_criados.append((p, Decimal(str(item["preco"]))))
        session.flush()

        print("📈 Gerando histórico de 180 dias...")
        hoje = datetime.now(timezone.utc)
        
        # Commit ofertas em batch separado
        for p, preco_base in produtos_criados:
            for f in random.sample(fornecedores, 3):
                variacao = Decimal(random.uniform(0.9, 1.2))
                oferta = OfertaProduto(
                    produto_id=p.id,
                    fornecedor_id=f.id,
                    preco_ofertado=preco_base * variacao,
                    estoque_disponivel=random.randint(50, 1000),
                    tenant_id=tenant_id
                )
                session.add(oferta)
        session.commit()
        
        # Histórico em batches menores
        for p, preco_base in produtos_criados:
            for d in range(180):
                data = hoje - timedelta(days=d)
                
                # Vendas (com ruído e tendencia)
                venda_qtd = max(0, int(random.gauss(5, 3)))
                if venda_qtd > 0:
                    venda = VendasHistoricas(
                        produto_id=p.id,
                        data_venda=data,
                        quantidade=venda_qtd,
                        receita=Decimal(venda_qtd) * preco_base,
                        tenant_id=tenant_id
                    )
                    session.add(venda)
                
                # Preços Históricos (um registro por semana)
                if d % 7 == 0:
                    variacao_hist = Decimal(random.uniform(0.85, 1.15))
                    phost = PrecosHistoricos(
                        produto_id=p.id,
                        fornecedor=random.choice(fornecedores).nome,
                        preco=preco_base * variacao_hist,
                        coletado_em=data,
                        is_synthetic=True,
                        tenant_id=tenant_id
                    )
                    session.add(phost)
            # Commit por produto para evitar timeout
            session.commit()

        print("📝 Criando ordens recentes e auditoria...")
        # Simular algumas ordens criadas nos últimos 10 dias
        for i in range(15):
            p, preco_base = random.choice(produtos_criados)
            f = random.choice(fornecedores)
            data_o = hoje - timedelta(days=random.randint(0, 10))
            status = random.choice(["pending", "approved", "rejected", "cancelled"])
            
            ordem = OrdemDeCompra(
                produto_id=p.id,
                fornecedor_id=f.id,
                quantidade=random.randint(10, 50),
                valor=preco_base * Decimal(1.1),
                status=status,
                origem=random.choice(["Manual", "Automática"]),
                data_criacao=data_o,
                data_aprovacao=data_o + timedelta(hours=2) if status == "approved" else None,
                justificativa="Reposição de estoque baseada em demanda histórica." if status != "pending" else None,
                tenant_id=tenant_id
            )
            session.add(ordem)

            # Auditoria para algumas ordens automáticas
            if ordem.origem == "Automática":
                audit = AuditoriaDecisao(
                    agente_nome="Otimizador de Compras",
                    sku=p.sku,
                    acao="approve_order",
                    decisao='{"status": "recommended", "savings_percent": 12.5}',
                    raciocinio=f"Recomendado compra de {p.nome} do fornecedor {f.nome} devido ao melhor preço e prazo de entrega.",
                    contexto=f"Estoque atual ({p.estoque_atual}) abaixo do mínimo ({p.estoque_minimo}).",
                    data_decisao=data_o,
                    tenant_id=tenant_id
                )
                session.add(audit)

        session.commit()
        print("✨ Demo Seed finalizado com sucesso!")

if __name__ == "__main__":
    seed_demo()
