"""CLI para configurar o ambiente de desenvolvimento, incluindo geração de dados e treinamento de modelo."""

from __future__ import annotations

import argparse
import logging
import random
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from faker import Faker
from sqlmodel import Session, delete, select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import engine
from app.ml.training import train_global_lgbm_model
from app.models.models import PrecosHistoricos, Produto, VendasHistoricas as Venda

LOGGER = logging.getLogger(__name__)
FAKER = Faker("pt_BR")

CATEGORIAS = [
    "Tecidos e Revestimentos",
    "Espumas e Enchimentos",
    "Estruturas de Madeira",
    "Ferragens e Acessórios",
    "Colas e Adesivos",
    "Ferramentas e Insumos de Produção",
    "Acabamentos",
]


def _generate_synthetic_products(session: Session, num_products: int) -> list[int]:
    """Gera e insere produtos sintéticos no banco de dados."""
    LOGGER.info(f"Gerando {num_products} produtos sintéticos...")
    FAKER.unique.clear()  # Limpa o histórico de valores únicos
    produtos_criados = []
    for _ in range(num_products):
        produto = Produto(
            nome=FAKER.unique.catch_phrase(),
            sku=FAKER.unique.ean(length=8),
            categoria=random.choice(CATEGORIAS),
            estoque_atual=random.randint(50, 5000),
            estoque_minimo=random.randint(20, 1000),
        )
        session.add(produto)
        produtos_criados.append(produto)

    session.commit()
    for produto in produtos_criados:
        session.refresh(produto)

    LOGGER.info(f"{len(produtos_criados)} produtos criados com sucesso.")
    return [p.id for p in produtos_criados if p.id is not None]


def _generate_synthetic_sales(
    session: Session, product_ids: list[int], start_date: date, end_date: date
) -> None:
    """Gera e insere vendas sintéticas para uma lista de produtos."""
    LOGGER.info(f"Gerando vendas sintéticas de {start_date} a {end_date}...")
    total_days = (end_date - start_date).days
    vendas_a_inserir = []

    for produto_id in product_ids:
        # Padrão de sazonalidade (ex: mais vendas nos finais de semana)
        dias_semana = np.array([(start_date + timedelta(days=i)).weekday() for i in range(total_days)])
        sazonalidade = np.sin(2 * np.pi * dias_semana / 7) * 2 + 5  # Base de 5, pico no domingo

        # Tendência de crescimento ao longo do tempo
        tendencia = np.linspace(0, 5, total_days)

        # Ruído aleatório
        ruido = np.random.normal(0, 1.5, total_days)

        # Vendas diárias = base + sazonalidade + tendência + ruído
        vendas_diarias = np.maximum(0, 10 + sazonalidade + tendencia + ruido).astype(int)

        for i, quantidade in enumerate(vendas_diarias):
            if quantidade > 0:
                preco_unitario = round(random.uniform(50.0, 250.0), 2)
                venda = Venda(
                    produto_id=produto_id,
                    data_venda=start_date + timedelta(days=i),
                    quantidade=int(quantidade),
                    receita=int(quantidade) * preco_unitario,
                )
                vendas_a_inserir.append(venda)

    session.add_all(vendas_a_inserir)
    session.commit()
    LOGGER.info(f"{len(vendas_a_inserir)} registros de vendas criados.")


def _generate_synthetic_prices(
    session: Session, product_ids: list[int], start_date: date, end_date: date
) -> None:
    """Gera e insere preços históricos sintéticos para uma lista de produtos."""
    LOGGER.info(f"Gerando histórico de preços de {start_date} a {end_date}...")
    precos_a_inserir = []
    for produto_id in product_ids:
        # Gera entre 120 e 150 pontos de preço para cada produto para atender ao requisito do modelo
        for _ in range(random.randint(500, 1500)):
            dias_aleatorios = random.randint(0, (end_date - start_date).days)
            data_preco = start_date + timedelta(days=dias_aleatorios)
            preco = PrecosHistoricos(
                produto_id=produto_id,
                preco=round(random.uniform(45.0, 230.0), 2),
                coletado_em=data_preco,
                is_synthetic=True,
            )
            precos_a_inserir.append(preco)

    session.add_all(precos_a_inserir)
    session.commit()
    LOGGER.info(f"{len(precos_a_inserir)} registros de preços criados.")


def run_seed(num_products: int, history_days: int) -> None:
    """Executa o processo de popular o banco com dados sintéticos."""
    LOGGER.info("Iniciando o processo de seed do banco de dados...")
    try:
        with Session(engine) as session:
            LOGGER.info("Limpando tabelas de vendas e produtos existentes...")
            session.exec(delete(PrecosHistoricos))
            session.exec(delete(Venda))
            session.exec(delete(Produto))
            session.commit()

            end_date = date.today()
            start_date = end_date - timedelta(days=history_days)

            product_ids = _generate_synthetic_products(session, num_products)
            if not product_ids:
                LOGGER.warning("Nenhum produto foi criado. Abortando a geração de vendas.")
                return

            _generate_synthetic_sales(session, product_ids, start_date, end_date)
            _generate_synthetic_prices(session, product_ids, start_date, end_date)

        LOGGER.info("Seed do banco de dados concluído com sucesso.")
    except Exception as e:
        LOGGER.error(f"Falha ao executar o seed do banco de dados: {e}", exc_info=True)
        sys.exit(1)


def run_training() -> None:
    """Executa o treinamento do modelo global LightGBM."""
    LOGGER.info("Iniciando o treinamento do modelo global...")
    try:
        train_global_lgbm_model()
        LOGGER.info("Treinamento do modelo concluído com sucesso.")
    except Exception as e:
        LOGGER.error(f"Falha durante o treinamento do modelo: {e}", exc_info=True)
        sys.exit(1)


def main() -> None:
    """Função principal para orquestrar as ações via CLI."""
    parser = argparse.ArgumentParser(description="Setup do ambiente de desenvolvimento.")
    parser.add_argument(
        "action",
        choices=["seed", "train", "all"],
        help="Ação a ser executada: 'seed' para popular o banco, 'train' para treinar o modelo, 'all' para ambos.",
    )
    parser.add_argument("--num-products", type=int, default=200, help="Número de produtos a serem gerados.")
    parser.add_argument("--history-days", type=int, default=365, help="Número de dias de histórico de vendas.")
    parser.add_argument("--skip-dotenv", action="store_true", help="Não carregar o arquivo .env.")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    if not args.skip_dotenv:
        load_dotenv()

    if args.action == "seed" or args.action == "all":
        run_seed(args.num_products, args.history_days)

    if args.action == "train" or args.action == "all":
        run_training()


if __name__ == "__main__":
    main()
