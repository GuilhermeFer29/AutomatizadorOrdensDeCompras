"""Mercado Livre scraping helpers backed by ScraperAPI."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote_plus

import httpx
import structlog
from bs4 import BeautifulSoup  # type: ignore[import-untyped]
from tenacity import RetryError, Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

LOGGER = structlog.get_logger(__name__)

SCRAPERAPI_ENDPOINT = "http://api.scraperapi.com"
SEARCH_URL_TEMPLATE = "https://lista.mercadolivre.com.br/{query}"
PRICE_SELECTORS: tuple[str, ...] = (
    "span.andes-money-amount__fraction",
    "span.price-tag-fraction",
    "span.price-tag-amount",
)
PRICE_PATTERN = re.compile(r"(?:\d{1,3}(?:\.\d{3})*|\d+)(?:,\d{2})?")


class ScraperAPIConfigurationError(RuntimeError):
    """Raised when ScraperAPI required configuration is missing."""


class ScraperAPIRequestError(RuntimeError):
    """Raised when ScraperAPI cannot deliver a valid response."""


@dataclass(slots=True)
class ScraperConfig:
    """Runtime configuration for ScraperAPI calls."""

    api_key: str
    timeout: float
    max_attempts: int
    min_backoff: float
    max_backoff: float


def scrape_mercadolivre(produto_nome: str) -> Optional[float]:
    """Fetch the price of the first Mercado Livre result for ``produto_nome``."""

    if not produto_nome:
        LOGGER.warning("Nome de produto vazio recebido para scraping do Mercado Livre.")
        return None

    try:
        config = _load_config()
    except ScraperAPIConfigurationError as error:
        LOGGER.error("Configuração da ScraperAPI ausente", error=str(error))
        return None

    try:
        html = _get_search_page(produto_nome=produto_nome, config=config)
    except ScraperAPIRequestError as error:
        LOGGER.error(
            "Falha ao recuperar página do Mercado Livre via ScraperAPI",
            produto_nome=produto_nome,
            error=str(error),
        )
        return None
    except RetryError as error:
        LOGGER.error(
            "ScraperAPI esgotou tentativas",
            produto_nome=produto_nome,
            tentativas=config.max_attempts,
            error=str(error.last_attempt.exception() if error.last_attempt else error),
        )
        return None

    price = _extract_price_from_html(html)
    if price is None:
        LOGGER.warning(
            "Nenhum preço encontrado no Mercado Livre",
            produto_nome=produto_nome,
        )
        return None

    LOGGER.info(
        "Preço obtido do Mercado Livre",
        produto_nome=produto_nome,
        preco=price,
    )
    return price


def _load_config() -> ScraperConfig:
    api_key = os.getenv("SCRAPERAPI_KEY")
    if not api_key:
        raise ScraperAPIConfigurationError("Variável SCRAPERAPI_KEY não configurada.")

    return ScraperConfig(
        api_key=api_key,
        timeout=float(os.getenv("SCRAPERAPI_TIMEOUT", "20")),
        max_attempts=int(os.getenv("SCRAPERAPI_MAX_ATTEMPTS", "3")),
        min_backoff=float(os.getenv("SCRAPERAPI_MIN_BACKOFF", "1")),
        max_backoff=float(os.getenv("SCRAPERAPI_MAX_BACKOFF", "10")),
    )


def _get_search_page(*, produto_nome: str, config: ScraperConfig) -> str:
    retrying = Retrying(
        stop=stop_after_attempt(config.max_attempts),
        wait=wait_exponential(
            multiplier=config.min_backoff,
            min=config.min_backoff,
            max=config.max_backoff,
        ),
        retry=retry_if_exception_type(ScraperAPIRequestError),
        reraise=True,
    )

    for attempt in retrying:
        with attempt:
            return _perform_scraperapi_request(produto_nome=produto_nome, config=config)

    raise ScraperAPIRequestError("Loop de tentativas encerrou sem retorno da ScraperAPI.")


def _perform_scraperapi_request(*, produto_nome: str, config: ScraperConfig) -> str:
    target_url = SEARCH_URL_TEMPLATE.format(query=quote_plus(produto_nome))
    params = {
        "api_key": config.api_key,
        "url": target_url,
    }

    LOGGER.info(
        "Disparando requisição à ScraperAPI",
        target_url=target_url,
    )

    try:
        response = httpx.get(SCRAPERAPI_ENDPOINT, params=params, timeout=config.timeout)
        response.raise_for_status()
    except httpx.TimeoutException as error:
        LOGGER.warning("Timeout ao chamar ScraperAPI", target_url=target_url, error=str(error))
        raise ScraperAPIRequestError("Timeout na ScraperAPI.") from error
    except httpx.HTTPStatusError as error:
        LOGGER.warning(
            "ScraperAPI retornou status inválido",
            target_url=target_url,
            status_code=error.response.status_code if error.response else None,
            error=str(error),
        )
        raise ScraperAPIRequestError("Status HTTP inválido retornado pela ScraperAPI.") from error
    except httpx.HTTPError as error:
        LOGGER.warning("Erro HTTP ao acessar ScraperAPI", target_url=target_url, error=str(error))
        raise ScraperAPIRequestError("Erro HTTP ao acessar ScraperAPI.") from error

    return response.text


def _extract_price_from_html(html: str) -> Optional[float]:
    soup = BeautifulSoup(html, "html.parser")
    candidate = soup.select_one("li.ui-search-layout__item")
    if candidate is None:
        candidate = soup.select_one("div.ui-search-result__content-wrapper")
    if candidate is None:
        LOGGER.debug("Nenhuma estrutura de item encontrada na página do Mercado Livre.")
        return None

    for selector in PRICE_SELECTORS:
        element = candidate.select_one(selector)
        if element:
            price = _parse_price_text(element.get_text(strip=True))
            if price is not None:
                return price

    text_block = candidate.get_text(separator=" ", strip=True)
    return _parse_price_text(text_block)


def _parse_price_text(text: str) -> Optional[float]:
    match = PRICE_PATTERN.search(text)
    if not match:
        return None

    raw_value = match.group(0)
    normalised = raw_value.replace(".", "").replace(",", ".")
    try:
        return float(normalised)
    except ValueError:
        LOGGER.debug("Falha ao converter preço para float", valor=raw_value)
        return None


__all__ = ["scrape_mercadolivre"]
