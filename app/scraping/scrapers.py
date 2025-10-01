from __future__ import annotations

import os
import random
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Mapping, Optional
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

try:  # pragma: no cover - Playwright might be unavailable in some environments.
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:  # pragma: no cover
    PlaywrightError = Exception  # type: ignore[assignment]
    PLAYWRIGHT_AVAILABLE = False

_USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4_1) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/16.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
)

_PRICE_PATTERN = re.compile(r"-?\d+[\d.,]*")


@dataclass(slots=True)
class ScrapeSpec:
    """Specification describing how to collect pricing information."""

    url: str
    price_selector: str
    currency: str = "BRL"
    headers: Optional[Mapping[str, str]] = None
    metadata: Optional[Mapping[str, Any]] = None


@dataclass(slots=True)
class ScrapeResult:
    """Structured response produced by the scraping helpers."""

    price: Decimal
    currency: str
    raw_text: str
    source: str
    metadata: Mapping[str, Any]


class ScrapingError(RuntimeError):
    """Raised whenever scraping fails across all strategies."""


def scrape_price(
    spec: ScrapeSpec,
    *,
    timeout: float = 30.0,
    proxies: Optional[Mapping[str, str]] = None,
) -> ScrapeResult:
    """Attempt to collect the price defined by ``spec``.

    The function prefers ScraperAPI (when the environment is configured) before
    trying Playwright and finally a direct ``httpx`` + ``BeautifulSoup`` flow.
    Each strategy is retried a few times with exponential backoff before
    falling back to the next option.
    """
    errors: list[str] = []

    strategies: tuple[tuple[str, bool, Callable[[], ScrapeResult]], ...] = (
        (
            "ScraperAPI",
            _is_scraperapi_enabled(),
            lambda: _scrape_with_httpx(
                spec=spec,
                timeout=timeout,
                proxies=None,
                use_scraperapi=True,
            ),
        ),
        (
            "Playwright",
            PLAYWRIGHT_AVAILABLE,
            lambda: _scrape_with_playwright(spec=spec, timeout=timeout, proxies=proxies),
        ),
        (
            "HTTPX fallback",
            True,
            lambda: _scrape_with_httpx(
                spec=spec,
                timeout=timeout,
                proxies=proxies,
                use_scraperapi=False,
            ),
        ),
    )

    for name, enabled, executor in strategies:
        if not enabled:
            continue
        try:
            return executor()
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name} failure: {exc}")

    raise ScrapingError("; ".join(errors))

def _scrape_with_playwright(
    *, spec: ScrapeSpec, timeout: float, proxies: Optional[Mapping[str, str]]
) -> ScrapeResult:
    """Collect pricing information through Playwright."""

    if not PLAYWRIGHT_AVAILABLE:
        raise ScrapingError("Playwright is not available in this environment.")

    headers = _build_headers(spec.headers)
    proxy_config = _build_proxy_argument(proxies)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(user_agent=headers["User-Agent"], proxy=proxy_config)
        page = context.new_page()
        page.set_extra_http_headers({k: v for k, v in headers.items() if k.lower() != "user-agent"})

        page.goto(spec.url, wait_until="networkidle", timeout=int(timeout * 1000))
        element = page.wait_for_selector(spec.price_selector, timeout=int(timeout * 1000))
        price_text = element.inner_text().strip()

        context.close()
        browser.close()

    metadata = dict(spec.metadata or {})
    metadata.update(
        {
            "requested_url": spec.url,
            "strategy": "playwright",
            "selector": spec.price_selector,
        }
    )

    price = _parse_price(price_text)
    return ScrapeResult(
        price=price,
        currency=spec.currency,
        raw_text=price_text,
        source="playwright",
        metadata=metadata,
    )


@retry(
    reraise=True,
    retry=retry_if_exception_type((httpx.HTTPError, ValueError, InvalidOperation)),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    stop=stop_after_attempt(3),
)
def _scrape_with_httpx(
    *,
    spec: ScrapeSpec,
    timeout: float,
    proxies: Optional[Mapping[str, str]],
    use_scraperapi: bool,
) -> ScrapeResult:
    """Collect pricing information through a traditional HTTP request."""

    headers = _build_headers(spec.headers)
    client_kwargs: dict[str, Any] = {"timeout": timeout, "headers": headers}
    if not use_scraperapi and proxies:
        client_kwargs["proxies"] = proxies

    request_url = _wrap_url_with_scraperapi(spec.url) if use_scraperapi else spec.url

    with httpx.Client(**client_kwargs) as client:
        response = client.get(request_url)
        response.raise_for_status()

    metadata = dict(spec.metadata or {})
    metadata.update(
        {
            "requested_url": spec.url,
            "effective_url": str(response.url),
            "status_code": response.status_code,
            "strategy": "scraperapi" if use_scraperapi else "httpx",
            "selector": spec.price_selector,
        }
    )

    soup = BeautifulSoup(response.text, "html.parser")
    element = soup.select_one(spec.price_selector)
    if element is None:
        raise ValueError(
            f"Elemento não encontrado com o seletor '{spec.price_selector}' na URL {spec.url}"
        )

    price_text = element.get_text(strip=True)
    price = _parse_price(price_text)
    return ScrapeResult(
        price=price,
        currency=spec.currency,
        raw_text=price_text,
        source="scraperapi" if use_scraperapi else "httpx",
        metadata=metadata,
    )


def _parse_price(raw_text: str) -> Decimal:
    """Transform a textual price into a :class:`~decimal.Decimal`."""

    match = _PRICE_PATTERN.search(raw_text)
    if not match:
        raise ValueError(f"Não foi possível identificar o preço em: {raw_text}")

    cleaned = match.group().replace(".", "").replace(",", ".")
    return Decimal(cleaned)


def _build_headers(custom: Optional[Mapping[str, str]]) -> Mapping[str, str]:
    """Compose HTTP headers using an optional custom mapping."""

    headers = {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
    }

    if custom:
        headers.update(custom)

    return headers


def _build_proxy_argument(proxies: Optional[Mapping[str, str]]) -> Optional[dict[str, str]]:
    """Translate proxy definitions to a Playwright compatible structure."""

    if not proxies:
        return None

    proxy_url = proxies.get("http") or proxies.get("https")
    if not proxy_url:
        return None

    return {"server": proxy_url}


def build_proxy_configuration_from_env() -> Mapping[str, str]:
    """Return the proxy configuration dictated by environment variables."""

    http_proxy = os.getenv("SCRAPING_HTTP_PROXY")
    https_proxy = os.getenv("SCRAPING_HTTPS_PROXY")

    config: dict[str, str] = {}
    if http_proxy:
        config["http"] = http_proxy
    if https_proxy:
        config["https"] = https_proxy

    return config


def _wrap_url_with_scraperapi(url: str) -> str:
    api_key = os.getenv("SCRAPERAPI_KEY")
    if not api_key:
        return url

    params = {
        "api_key": api_key,
        "url": url,
    }

    keep_headers_flag = os.getenv("SCRAPERAPI_KEEP_HEADERS", "false").lower()
    if keep_headers_flag in {"1", "true", "yes"}:
        params["keep_headers"] = "true"

    country = os.getenv("SCRAPERAPI_COUNTRY")
    if country:
        params["country_code"] = country

    render_flag = os.getenv("SCRAPERAPI_RENDER", "true").lower()
    if render_flag in {"1", "true", "yes"}:
        params["render"] = "true"

    premium = os.getenv("SCRAPERAPI_PREMIUM", "false").lower()
    if premium in {"1", "true", "yes"}:
        params["premium"] = "true"

    device_type = os.getenv("SCRAPERAPI_DEVICE_TYPE")
    if device_type:
        params["device_type"] = device_type

    autoparse = os.getenv("SCRAPERAPI_AUTOPARSE", "false").lower()
    if autoparse in {"1", "true", "yes"}:
        params["autoparse"] = "true"

    return f"https://api.scraperapi.com/?{urlencode(params)}"


def _is_scraperapi_enabled() -> bool:
    return bool(os.getenv("SCRAPERAPI_KEY"))


__all__ = [
    "ScrapeSpec",
    "ScrapeResult",
    "ScrapingError",
    "build_proxy_configuration_from_env",
    "scrape_price",
]
