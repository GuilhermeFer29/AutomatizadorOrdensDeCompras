"""Generate an extensive product and sales seed dataset for the project."""

from __future__ import annotations

import argparse
import csv
import math
import random
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, List, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"


@dataclass(frozen=True)
class IndustryProfile:
    prefix: str
    category: str
    bases: Sequence[str]
    materials: Sequence[str]
    finishes: Sequence[str]
    dimensions: Sequence[str]
    price_range: tuple[float, float]
    stock_range: tuple[int, int]
    min_stock_range: tuple[int, int]


@dataclass(frozen=True)
class ProductRecord:
    sku: str
    name: str
    category: str
    stock_current: int
    stock_minimum: int
    unit_price: float


INDUSTRY_PROFILES: tuple[IndustryProfile, ...] = (
    IndustryProfile(
        prefix="TXT",
        category="Indústria Têxtil",
        bases=(
            "Tecido",
            "Malha",
            "Lona",
            "Sarja",
            "Feltro",
            "Gorgorão",
            "Renda",
            "Brim",
        ),
        materials=(
            "Algodão",
            "Poliéster",
            "Viscose",
            "Linho",
            "Modal",
            "Denim",
            "Juta",
            "Poliamida",
        ),
        finishes=("Cru", "Estampado", "Tingido", "Impermeável", "Resinado"),
        dimensions=(
            "120gsm Largura 1,40m",
            "150gsm Largura 1,60m",
            "180gsm Largura 1,80m",
            "220gsm Largura 2,00m",
            "260gsm Largura 2,20m",
        ),
        price_range=(12.0, 98.0),
        stock_range=(400, 1600),
        min_stock_range=(60, 220),
    ),
    IndustryProfile(
        prefix="EST",
        category="Indústria de Estofados",
        bases=(
            "Espuma",
            "Tecido Suede",
            "Couro Sintético",
            "Fibra Siliconada",
            "Manta Acrílica",
            "Tecido Jacquard",
            "Tecido Chenille",
            "Percal",
        ),
        materials=(
            "Densidade 23",
            "Densidade 28",
            "Densidade 33",
            "Densidade 45",
            "Soft",
            "Premium",
            "Antichama",
            "Impermeável",
        ),
        finishes=(
            "Bege",
            "Cinza",
            "Azul",
            "Marrom",
            "Verde",
            "Grafite",
            "Vinho",
            "Caramelo",
        ),
        dimensions=(
            "1,00m x 1,50m",
            "1,20m x 2,00m",
            "1,40m x 2,10m",
            "1,50m x 2,20m",
            "1,80m x 2,40m",
        ),
        price_range=(35.0, 185.0),
        stock_range=(250, 900),
        min_stock_range=(40, 160),
    ),
    IndustryProfile(
        prefix="MOV",
        category="Componentes para Indústria de Móveis",
        bases=(
            "Puxador",
            "Dobradiça",
            "Corrediça",
            "Dobradiça Caneco",
            "Perfil PVC",
            "Tampo MDF",
            "Prateleira MDP",
            "Parafuso Confirmat",
        ),
        materials=(
            "Metálico",
            "Plástico",
            "Alumínio",
            "Aço Inox",
            "Aço Carbono",
            "MDF",
            "MDP",
            "Madeira Tauari",
        ),
        finishes=(
            "Escovado",
            "Cromado",
            "Preto Fosco",
            "Branco",
            "Champagne",
            "Níquel",
            "Texturizado",
            "Verniz Fosco",
        ),
        dimensions=(
            "96mm",
            "128mm",
            "160mm",
            "300mm",
            "400mm",
            "450mm",
            "500mm",
            "600mm",
        ),
        price_range=(8.5, 145.0),
        stock_range=(350, 1200),
        min_stock_range=(50, 200),
    ),
    IndustryProfile(
        prefix="MET",
        category="Indústria Metalúrgica",
        bases=(
            "Chapa",
            "Barra",
            "Perfil U",
            "Perfil I",
            "Tubo",
            "Cantoneira",
            "Vergalhão",
            "Fio Máquina",
        ),
        materials=(
            "Aço Carbono",
            "Aço Inox",
            "Alumínio",
            "Latão",
            "Cobre",
            "Galvanizado",
            "Zincado",
            "Revestido",
        ),
        finishes=(
            "Quente",
            "Frio",
            "Decapado",
            "Laminado",
            "Estanhado",
            "Polido",
            "Tratado",
            "Decapado e Oleado",
        ),
        dimensions=(
            "1,20m x 2,40m",
            "1,50m x 3,00m",
            "6m",
            "8m",
            "10m",
            "12m",
            "Estrutural Pesado",
            "Estrutural Leve",
        ),
        price_range=(58.0, 620.0),
        stock_range=(120, 700),
        min_stock_range=(20, 120),
    ),
    IndustryProfile(
        prefix="AUT",
        category="Autopeças Industriais",
        bases=(
            "Filtro de Óleo",
            "Filtro de Ar",
            "Filtro de Combustível",
            "Pastilha de Freio",
            "Amortecedor",
            "Rolamento",
            "Correia Dentada",
            "Bucha de Suspensão",
        ),
        materials=(
            "Linha Pesada",
            "Linha Leve",
            "Utilitário",
            "Agrícola",
            "Industrial",
            "Alta Performance",
            "Original",
            "Reforçado",
        ),
        finishes=(
            "Chevrolet",
            "Volkswagen",
            "Fiat",
            "Ford",
            "Mercedes",
            "Scania",
            "Volvo",
            "Iveco",
        ),
        dimensions=(
            "Código 101",
            "Código 205",
            "Código 307",
            "Código 411",
            "Código 518",
            "Código 623",
            "Código 735",
            "Código 842",
        ),
        price_range=(28.0, 780.0),
        stock_range=(80, 450),
        min_stock_range=(15, 90),
    ),
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate large product and sales seed CSV files.")
    parser.add_argument("--total-products", type=int, default=1000, help="Total number of products to generate.")
    parser.add_argument(
        "--months",
        type=int,
        default=12,
        help="Number of monthly sales records to generate per product.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20240930,
        help="Random seed for reproducibility.",
    )
    parser.add_argument(
        "--products-output",
        type=Path,
        default=DATA_DIR / "products_seed.csv",
        help="Path to write the generated products CSV.",
    )
    parser.add_argument(
        "--sales-output",
        type=Path,
        default=DATA_DIR / "sample_vendas.csv",
        help="Path to write the generated sales CSV.",
    )
    return parser.parse_args()


def ensure_output_directory(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def distribute_counts(total: int, profiles: Sequence[IndustryProfile]) -> List[int]:
    base = total // len(profiles)
    remainder = total % len(profiles)
    counts = [base] * len(profiles)
    for index in range(remainder):
        counts[index] += 1
    return counts


def build_name_pool(profile: IndustryProfile) -> List[str]:
    names: List[str] = []
    for base in profile.bases:
        for material in profile.materials:
            for finish in profile.finishes:
                for dimension in profile.dimensions:
                    names.append(f"{base} {material} {finish} {dimension}")
    return names


def generate_products(args: argparse.Namespace) -> List[ProductRecord]:
    rng = random.Random(args.seed)
    counts = distribute_counts(args.total_products, INDUSTRY_PROFILES)
    products: List[ProductRecord] = []

    for profile, count in zip(INDUSTRY_PROFILES, counts):
        name_pool = build_name_pool(profile)
        if count > len(name_pool):
            raise ValueError(
                f"Perfil {profile.category} não possui combinações suficientes (solicitado {count}, disponível {len(name_pool)})."
            )
        rng.shuffle(name_pool)
        for index in range(count):
            name = name_pool[index]
            sku = f"{profile.prefix}-{index + 1:04d}"
            stock_current = rng.randint(*profile.stock_range)
            stock_minimum = rng.randint(*profile.min_stock_range)
            stock_minimum = min(stock_minimum, max(stock_current // 3, 10))
            unit_price = round(rng.uniform(*profile.price_range), 2)
            products.append(
                ProductRecord(
                    sku=sku,
                    name=name,
                    category=profile.category,
                    stock_current=stock_current,
                    stock_minimum=stock_minimum,
                    unit_price=unit_price,
                )
            )

    products.sort(key=lambda record: record.sku)
    return products


def write_products_csv(products: Iterable[ProductRecord], output_path: Path) -> None:
    ensure_output_directory(output_path)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sku", "nome", "categoria", "estoque_atual", "estoque_minimo"])
        for product in products:
            writer.writerow(
                [
                    product.sku,
                    product.name,
                    product.category,
                    product.stock_current,
                    product.stock_minimum,
                ]
            )


def write_sales_csv(products: Iterable[ProductRecord], months: int, output_path: Path) -> None:
    ensure_output_directory(output_path)
    rng = random.Random(42)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "sku",
                "nome",
                "data_venda",
                "quantidade",
                "receita",
                "categoria",
                "estoque_atual",
                "estoque_minimo",
            ]
        )
        for product in products:
            for month_offset in range(months):
                year = 2024 + (month_offset // 12)
                month = (month_offset % 12) + 1
                sale_day = rng.randint(1, 28)
                sale_date = date(year, month, sale_day)
                quantity = rng.randint(8, 240)
                variance = rng.uniform(0.92, 1.18)
                revenue = round(quantity * product.unit_price * variance, 2)
                writer.writerow(
                    [
                        product.sku,
                        product.name,
                        sale_date.isoformat(),
                        quantity,
                        f"{revenue:.2f}",
                        product.category,
                        product.stock_current,
                        product.stock_minimum,
                    ]
                )


def main() -> None:
    args = parse_arguments()
    products = generate_products(args)
    write_products_csv(products, args.products_output)
    write_sales_csv(products, args.months, args.sales_output)
    print(
        f"Produtos gerados: {len(products)} | Arquivo produtos: {args.products_output} | Arquivo vendas: {args.sales_output}"
    )


if __name__ == "__main__":
    main()
