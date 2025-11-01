"""Populate the products catalogue from a CSV definition."""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlmodel import Session, delete, select

from app.core.database import engine
from app.models.models import ModeloPredicao, PrecosHistoricos, Produto, VendasHistoricas


@dataclass(frozen=True)
class ProductSeed:
    """Structure representing one product row from the seed file."""

    sku: str
    nome: str
    categoria: str
    estoque_atual: int
    estoque_minimo: int


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Populate the produtos table from a CSV file.")
    parser.add_argument(
        "csv_path",
        type=Path,
        nargs="?",
        default=Path("data/products_seed.csv"),
        help="Path to the CSV file containing product definitions.",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Remove existing products before seeding new ones.",
    )
    return parser.parse_args()


REQUIRED_COLUMNS = {"sku", "nome", "categoria", "estoque_atual", "estoque_minimo"}


def read_product_seed(csv_path: Path) -> List[ProductSeed]:
    _ensure_file_exists(csv_path)
    rows = _read_csv_rows(csv_path)
    seeds = [_build_product_seed(row) for row in rows]
    if not seeds:
        raise ValueError("O arquivo CSV não contém produtos para inserir.")
    return seeds


def _ensure_file_exists(csv_path: Path) -> None:
    if not csv_path.exists():
        raise FileNotFoundError(f"Arquivo CSV não encontrado: {csv_path}")


def _read_csv_rows(csv_path: Path) -> List[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        _ensure_required_columns(reader.fieldnames)
        return list(reader)


def _ensure_required_columns(fieldnames: Iterable[str] | None) -> None:
    missing = REQUIRED_COLUMNS - set(fieldnames or [])
    if missing:
        raise ValueError(f"Colunas ausentes no CSV: {', '.join(sorted(missing))}")


def _build_product_seed(row: dict[str, str]) -> ProductSeed:
    return ProductSeed(
        sku=row["sku"].strip(),
        nome=row["nome"].strip(),
        categoria=row["categoria"].strip(),
        estoque_atual=int(row.get("estoque_atual") or 0),
        estoque_minimo=int(row.get("estoque_minimo") or 0),
    )


def truncate_products(session: Session) -> None:
    """Remove all existing products and dependent records from the catalogue."""

    session.exec(delete(ModeloPredicao))
    session.exec(delete(PrecosHistoricos))
    session.exec(delete(VendasHistoricas))
    session.exec(delete(Produto))
    session.commit()


def seed_products(session: Session, products: Iterable[ProductSeed]) -> None:
    """Insert or update products in the catalogue."""

    products_list = list(products)
    if not products_list:
        return

    sku_lookup = {seed.sku for seed in products_list}

    existing_by_sku = {
        produto.sku: produto
        for produto in session.exec(select(Produto).where(Produto.sku.in_(sku_lookup))).all()
    }

    inserted = 0
    updated = 0

    for seed in products_list:
        produto = existing_by_sku.get(seed.sku)
        if produto is None:
            session.add(
                Produto(
                    sku=seed.sku,
                    nome=seed.nome,
                    categoria=seed.categoria,
                    estoque_atual=seed.estoque_atual,
                    estoque_minimo=seed.estoque_minimo,
                )
            )
            inserted += 1
        else:
            produto.nome = seed.nome
            produto.categoria = seed.categoria
            produto.estoque_atual = seed.estoque_atual
            produto.estoque_minimo = seed.estoque_minimo
            updated += 1

    session.commit()
    print(f"Produtos inseridos: {inserted}")
    print(f"Produtos atualizados: {updated}")


def main() -> None:
    args = parse_arguments()
    products = read_product_seed(args.csv_path)

    with Session(engine) as session:
        if args.truncate:
            truncate_products(session)
        seed_products(session, products)


if __name__ == "__main__":
    main()
