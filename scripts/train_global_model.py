"""CLI utility to train a single Prophet model over the entire price catalogue."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ml.training import train_global_model  # noqa: E402

LOGGER = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train Prophet model using the full catalogue history.")
    parser.add_argument(
        "--skip-dotenv",
        action="store_true",
        help="Do not load environment variables from the .env file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    configure_logging()

    if not args.skip_dotenv:
        load_dotenv()

    LOGGER.info("Iniciando treinamento global do catálogo")
    pdf_path = train_global_model()
    LOGGER.info("Treinamento global concluído: %s", pdf_path)


if __name__ == "__main__":
    main()
