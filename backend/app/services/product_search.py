"""Product search and price comparison service.

Provides a unified interface for searching real products and prices from
external sources. Designed to be integrated with the AI copilot for
shopping-related queries.

Architecture:
- Source adapters implement the ProductSource protocol
- SearchService coordinates multiple sources and normalizes results
- Results include price, currency, seller, link, and metadata
- No purchases or bookings are performed; read-only price discovery
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlencode, urljoin, urlparse

import httpx

logger = logging.getLogger("arqau.product_search")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProductOffer:
    """A single product offer from a specific seller."""
    source: str                    # Source identifier (e.g., "kaspi", "wildberries")
    product_id: str                # Source-specific product ID
    title: str                     # Product title
    price_minor: int               # Price in minor units (tiyin for KZT)
    currency: str = "KZT"          # Currency code
    seller: str | None = None      # Seller name
    seller_rating: float | None = None
    url: str | None = None         # Deep link to product page
    image_url: str | None = None   # Product image
    availability: str | None = None  # e.g., "in_stock", "limited", "preorder"
    delivery_info: str | None = None  # Delivery cost/time info
    fetched_at: datetime = field(default_factory=datetime.utcnow)
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchResult:
    """Normalized search results from one or more sources."""
    query: str
    offers: list[ProductOffer]
    total_found: int
    sources_queried: list[str]
    errors: list[str] = field(default_factory=list)
    searched_at: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Source protocol
# ---------------------------------------------------------------------------

class ProductSource(ABC):
    """Abstract base for product search sources."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique source identifier."""
        pass

    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> list[ProductOffer]:
        """Search for products matching the query."""
        pass

    async def health_check(self) -> bool:
        """Optional health check for the source."""
        return True


# ---------------------------------------------------------------------------
# HTTP client with common settings
# ---------------------------------------------------------------------------

SEARCH_TIMEOUT = httpx.Timeout(connect=3.0, read=8.0, write=5.0, pool=3.0)

async def _get_client() -> httpx.AsyncClient:
    """Create a shared HTTP client for product search."""
    return httpx.AsyncClient(
        timeout=SEARCH_TIMEOUT,
        headers={
            "User-Agent": "ARQAU-PriceBot/1.0 (+https://arqau.kz)",
            "Accept": "application/json",
        },
        follow_redirects=True,
    )


# ---------------------------------------------------------------------------
# Example source: Kaspi.kz (requires API key, placeholder structure)
# ---------------------------------------------------------------------------

class KaspiSource(ProductSource):
    """Kaspi.kz product search.

    Requires API key from Kaspi Merchant Cabinet.
    Documentation: https://kaspi.kz/merchantcabinet/api/docs
    """

    def __init__(self, api_key: str | None = None, base_url: str = "https://api.kaspi.kz"):
        self._api_key = api_key
        self._base_url = base_url
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return "kaspi"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"User-Agent": "ARQAU-PriceBot/1.0"}
            if self._api_key:
                headers["X-Auth-Token"] = self._api_key
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=SEARCH_TIMEOUT,
                headers=headers,
            )
        return self._client

    async def search(self, query: str, limit: int = 10) -> list[ProductOffer]:
        if not self._api_key:
            logger.warning("Kaspi API key not configured, skipping source")
            return []

        client = await self._get_client()
        try:
            # Kaspi search endpoint (example structure)
            params = {
                "q": query,
                "limit": limit,
                "sort": "price_asc",
            }
            resp = await client.get("/api/v1/products/search", params=params)
            resp.raise_for_status()
            data = resp.json()

            offers = []
            for item in data.get("items", [])[:limit]:
                offers.append(ProductOffer(
                    source=self.name,
                    product_id=str(item.get("id", "")),
                    title=item.get("name", ""),
                    price_minor=int(item.get("price", 0) * 100),  # Convert to minor units
                    currency=item.get("currency", "KZT"),
                    seller=item.get("merchant", {}).get("name"),
                    seller_rating=item.get("merchant", {}).get("rating"),
                    url=item.get("url"),
                    image_url=item.get("image"),
                    availability=item.get("availability"),
                    delivery_info=item.get("delivery"),
                    raw_data=item,
                ))
            return offers

        except httpx.HTTPError as e:
            logger.error("Kaspi search failed: %s", e)
            return []
        except Exception as e:  # noqa: BLE001
            logger.exception("Unexpected error in Kaspi search")
            return []


# ---------------------------------------------------------------------------
# Example source: Wildberries (placeholder)
# ---------------------------------------------------------------------------

class WildberriesSource(ProductSource):
    """Wildberries product search placeholder.

    Wildberries API requires partner registration.
    """

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key

    @property
    def name(self) -> str:
        return "wildberries"

    async def search(self, query: str, limit: int = 10) -> list[ProductOffer]:
        if not self._api_key:
            logger.warning("Wildberries API key not configured, skipping source")
            return []
        # Implementation would go here
        return []


# ---------------------------------------------------------------------------
# Mock source for development/testing (no API key needed)
# ---------------------------------------------------------------------------

class MockProductSource(ProductSource):
    """Mock product source for development and testing.

    Returns deterministic fake data. NOT for production use.
    """

    @property
    def name(self) -> str:
        return "mock"

    async def search(self, query: str, limit: int = 10) -> list[ProductOffer]:
        # Deterministic mock data based on query hash
        query_hash = hash(query.lower().strip()) % 1000
        base_price = 50000 + (query_hash % 10) * 25000

        mock_offers = [
            ProductOffer(
                source=self.name,
                product_id=f"mock-{query_hash}-1",
                title=f"{query.title()} - Basic Model",
                price_minor=base_price * 100,
                currency="KZT",
                seller="Mock Seller 1",
                seller_rating=4.5,
                url=f"https://mock.example.com/product/{query_hash}-1",
                image_url=f"https://mock.example.com/images/{query_hash}-1.jpg",
                availability="in_stock",
                delivery_info="Бесплатно от 50 000 ₸",
                raw_data={"mock": True},
            ),
            ProductOffer(
                source=self.name,
                product_id=f"mock-{query_hash}-2",
                title=f"{query.title()} - Pro Model",
                price_minor=(base_price + 150000) * 100,
                currency="KZT",
                seller="Mock Seller 2",
                seller_rating=4.2,
                url=f"https://mock.example.com/product/{query_hash}-2",
                image_url=f"https://mock.example.com/images/{query_hash}-2.jpg",
                availability="limited",
                delivery_info="Доставка 2 500 ₸",
                raw_data={"mock": True},
            ),
        ]
        return mock_offers[:limit]


# ---------------------------------------------------------------------------
# Search service
# ---------------------------------------------------------------------------

class ProductSearchService:
    """Coordinates product search across multiple sources."""

    def __init__(self, sources: list[ProductSource] | None = None):
        self._sources = sources or []
        self._mock_source = MockProductSource()

    def add_source(self, source: ProductSource) -> None:
        """Add a product source."""
        self._sources.append(source)

    def set_mock_enabled(self, enabled: bool) -> None:
        """Enable/disable mock source (for development)."""
        if enabled and self._mock_source not in self._sources:
            self._sources.insert(0, self._mock_source)
        elif not enabled and self._mock_source in self._sources:
            self._sources.remove(self._mock_source)

    async def search(
        self,
        query: str,
        limit: int = 10,
        sources: list[str] | None = None,
    ) -> SearchResult:
        """Search across all enabled sources."""
        if not query or not query.strip():
            return SearchResult(
                query=query,
                offers=[],
                total_found=0,
                sources_queried=[],
                errors=["Empty query"],
            )

        # Filter sources if requested
        active_sources = self._sources
        if sources:
            active_sources = [s for s in self._sources if s.name in sources]

        if not active_sources:
            # Fallback to mock if no sources available
            active_sources = [self._mock_source]

        all_offers: list[ProductOffer] = []
        queried = []
        errors = []

        for source in active_sources:
            queried.append(source.name)
            try:
                offers = await source.search(query, limit=limit)
                all_offers.extend(offers)
            except Exception as e:  # noqa: BLE001
                logger.exception("Source %s failed", source.name)
                errors.append(f"{source.name}: {e}")

        # Sort by price ascending
        all_offers.sort(key=lambda o: o.price_minor)

        return SearchResult(
            query=query,
            offers=all_offers[:limit],
            total_found=len(all_offers),
            sources_queried=queried,
            errors=errors,
        )

    async def health_check_all(self) -> dict[str, bool]:
        """Check health of all sources."""
        results = {}
        for source in self._sources:
            try:
                results[source.name] = await source.health_check()
            except Exception:  # noqa: BLE001
                results[source.name] = False
        return results


# ---------------------------------------------------------------------------
# Global service instance (configured at startup)
# ---------------------------------------------------------------------------

_product_search_service: ProductSearchService | None = None


def get_product_search_service() -> ProductSearchService:
    """Get or create the global product search service."""
    global _product_search_service
    if _product_search_service is None:
        _product_search_service = ProductSearchService()
        # Enable mock by default for development
        _product_search_service.set_mock_enabled(True)
    return _product_search_service


def configure_product_search(
    sources: list[ProductSource] | None = None,
    mock_enabled: bool = True,
) -> ProductSearchService:
    """Configure the global product search service."""
    global _product_search_service
    _product_search_service = ProductSearchService(sources)
    if mock_enabled:
        _product_search_service.set_mock_enabled(True)
    return _product_search_service


# ---------------------------------------------------------------------------
# Query classification (simple heuristic)
# ---------------------------------------------------------------------------

_SHOPPING_KEYWORDS = (
    "купить", "найди", "поиск", "цена", "стоимость",
    "товар", "продукт", "модель", "ноутбук", "телефон", "смартфон",
    "телевизор", "холодильник", "стиральная", "пылесос", "наушники",
    "планшет", "монитор", "видеокарта", "процессор", "память", "ssd",
    "buy", "find", "search", "price", "cost", "product",
    "laptop", "phone", "smartphone", "tv", "fridge", "washer",
    "vacuum", "headphones", "tablet", "monitor", "gpu", "cpu", "ram",
)

def is_shopping_query(message: str) -> bool:
    """Heuristic: detect if user is asking for product search."""
    lowered = message.lower()
    return any(kw in lowered for kw in _SHOPPING_KEYWORDS)


# ---------------------------------------------------------------------------
# Apify Kaspi.kz Product Search source (skeleton, no network calls without token)
# ---------------------------------------------------------------------------

class ApifyKaspiSource(ProductSource):
    """Apify Actor: yadroo/kaspi-kz-products

    Skeleton implementation — no network calls without a valid token.
    Full implementation requires confirming Actor output schema.
    """

    DEFAULT_ACTOR_ID = "yadroo/kaspi-kz-products"
    DEFAULT_CITY_ID = "750000000"  # Almaty
    DEFAULT_MAX_ITEMS = 10

    def __init__(
        self,
        token: str | None = None,
        actor_id: str = DEFAULT_ACTOR_ID,
        base_url: str = "https://api.apify.com/v2",
    ):
        self._token = token
        self._actor_id = actor_id
        self._base_url = base_url
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return "apify-kaspi"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"User-Agent": "ARQAU-PriceBot/1.0"}
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=SEARCH_TIMEOUT,
                headers=headers,
            )
        return self._client

    async def search(self, query: str, limit: int = 10) -> list[ProductOffer]:
        """Search products via Apify Actor.

        Returns empty list if token is not configured — no network call is made.
        """
        if not self._token:
            logger.warning("Apify token not configured, skipping source: %s", self.name)
            return []

        if not query or not query.strip():
            return []

        # TODO: Implement full flow when Actor output schema is confirmed:
        # 1. POST /acts/{actor_id}/runs with input {query, maxItems: limit, cityId, includeOffers: true}
        # 2. Poll run status until SUCCEEDED/FAILED (with timeout)
        # 3. GET /actor-runs/{run_id}/dataset/items
        # 4. Map items to ProductOffer

        logger.info("ApifyKaspiSource.search called with query=%r, limit=%d (not implemented)", query, limit)
        return []

    async def health_check(self) -> bool:
        if not self._token:
            return False
        try:
            client = await self._get_client()
            resp = await client.get("/acts/me", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False


# ---------------------------------------------------------------------------
# market-sources Kaspi.kz adapter (lazy import, safe without dependency)
# ---------------------------------------------------------------------------

class MarketSourcesKaspiAdapter(ProductSource):
    """Adapter for octrow/market-sources KaspiSource.

    Uses lazy import so the application works without the library installed.
    Implements ProductSource protocol.
    """

    _MARKET_SOURCES_AVAILABLE: bool | None = None
    _KASPI_SOURCE_CLS: type | None = None

    def __init__(
        self,
        city: str = "almaty",
        client: Any | None = None,
    ):
        """
        Args:
            city: City for search (Kaspi city code or name).
            client: Optional pre-configured KaspiSource instance for testing.
                    If provided, lazy import is skipped. The caller retains
                    ownership and is responsible for closing it.
        """
        self._city = city
        self._provided_client = client
        self._client: Any | None = None
        self._owns_client = client is None  # Track if we created the client

    @classmethod
    def _ensure_import(cls) -> bool:
        """Lazy import of market_sources. Returns True if available."""
        if cls._MARKET_SOURCES_AVAILABLE is not None:
            return cls._MARKET_SOURCES_AVAILABLE

        try:
            from market_sources import KaspiSource  # type: ignore
            cls._KASPI_SOURCE_CLS = KaspiSource
            cls._MARKET_SOURCES_AVAILABLE = True
            return True
        except Exception:
            cls._MARKET_SOURCES_AVAILABLE = False
            cls._KASPI_SOURCE_CLS = None
            return False

    @property
    def name(self) -> str:
        return "market-sources-kaspi"

    def _get_client(self) -> Any:
        """Get or create the underlying KaspiSource client."""
        if self._provided_client is not None:
            return self._provided_client

        if self._client is None:
            if not self._ensure_import():
                raise RuntimeError("market-sources library not installed")
            self._client = self._KASPI_SOURCE_CLS()  # type: ignore
        return self._client

    async def search(self, query: str, limit: int = 10) -> list[ProductOffer]:
        """Search products via market-sources KaspiSource.

        Returns empty list if library not installed — no network call is made.
        """
        if not query or not query.strip():
            return []

        if not self._ensure_import():
            logger.warning(
                "market-sources library not installed, skipping source: %s",
                self.name,
            )
            return []

        client = self._get_client()

        try:
            # Step 1: Search for products
            # market-sources KaspiSource.search(query, city) -> list[RawProduct]
            products = await client.search(query, city=self._city)

            if not products:
                return []

            # Step 2: For each product, fetch offers to get prices and sellers
            offers_result: list[ProductOffer] = []

            for product in products[:limit]:
                try:
                    # Pass city to offers() per confirmed contract
                    product_offers = await client.offers(product.product_id, city=self._city)
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        "Failed to fetch offers for product %s: %s",
                        getattr(product, "product_id", "unknown"),
                        e,
                    )
                    continue

                if not product_offers:
                    continue

                # Take the cheapest offer for this product
                cheapest_offer = min(
                    product_offers,
                    key=lambda o: o.price if o.price is not None else float("inf"),
                )

                # Convert and validate price using Decimal for precision
                price_minor = self._convert_price_to_minor(cheapest_offer.price)
                if price_minor is None:
                    logger.debug(
                        "Skipping product %s: invalid price %s",
                        getattr(product, "product_id", "unknown"),
                        cheapest_offer.price,
                    )
                    continue

                # Validate required fields
                title = getattr(product, "title", None) or getattr(product, "name", None)
                if not title:
                    logger.debug(
                        "Skipping product %s: empty title",
                        getattr(product, "product_id", "unknown"),
                    )
                    continue

                url = getattr(product, "url", None)
                if not url or not self._is_valid_url(url):
                    logger.debug(
                        "Skipping product %s: missing or invalid URL (%s)",
                        getattr(product, "product_id", "unknown"),
                        url,
                    )
                    continue

                # Build availability string
                availability = "in_stock" if getattr(cheapest_offer, "in_stock", False) else "out_of_stock"

                # Build delivery info
                delivery_parts = []
                if getattr(cheapest_offer, "delivery", None):
                    delivery_parts.append(str(cheapest_offer.delivery))
                if getattr(cheapest_offer, "delivery_cost", None) is not None:
                    delivery_parts.append(f"{cheapest_offer.delivery_cost} ₸")
                if getattr(cheapest_offer, "delivery_date", None):
                    delivery_parts.append(str(cheapest_offer.delivery_date))
                delivery_info = ", ".join(delivery_parts) if delivery_parts else None

                # Build raw_data for debugging
                raw_data = {
                    "product": product.model_dump() if hasattr(product, "model_dump") else str(product),
                    "offer": cheapest_offer.model_dump() if hasattr(cheapest_offer, "model_dump") else str(cheapest_offer),
                }

                offers_result.append(ProductOffer(
                    source=self.name,
                    product_id=str(getattr(product, "product_id", "") or getattr(product, "id", "")),
                    title=str(title),
                    price_minor=price_minor,
                    currency="KZT",
                    seller=getattr(cheapest_offer, "seller", None),
                    seller_rating=getattr(cheapest_offer, "merchant_rating", None),
                    url=str(url) if url else None,
                    image_url=getattr(product, "image_url", None),
                    availability=availability,
                    delivery_info=delivery_info,
                    raw_data=raw_data,
                ))

                if len(offers_result) >= limit:
                    break

            return offers_result

        except Exception as e:  # noqa: BLE001
            logger.exception("MarketSourcesKaspiAdapter search failed: %s", e)
            return []

    def _convert_price_to_minor(self, price: Any) -> int | None:
        """Convert price from KZT (major units) to tiyin (minor units) using Decimal.

        Args:
            price: Price in KZT (float, int, str, Decimal, or None)

        Returns:
            Price in tiyin (int) or None if invalid
        """
        if price is None:
            return None

        try:
            # Convert to string first to avoid binary floating-point issues with Decimal
            # e.g., Decimal(379500.5) != Decimal("379500.5") in some cases
            price_str = str(price)
            decimal_price = Decimal(price_str)
            
            # Reject NaN and Infinity explicitly
            if decimal_price.is_nan() or decimal_price.is_infinite():
                return None
            
            if decimal_price < 0:
                return None
            
            # Convert KZT to tiyin (1 KZT = 100 tiyin)
            price_minor = int((decimal_price * 100).to_integral_value())
            return price_minor
        except (InvalidOperation, ValueError, TypeError):
            return None

    async def health_check(self) -> bool:
        if not self._ensure_import():
            return False
        try:
            # Basic health check - just verify client can be created
            self._get_client()
            return True
        except Exception:
            return False

    def _is_valid_url(self, url: str | None) -> bool:
        """Validate that URL is absolute HTTP/HTTPS."""
        if not url:
            return False
        try:
            parsed = urlparse(str(url))
            return parsed.scheme in ("http", "https") and bool(parsed.netloc)
        except Exception:
            return False

    async def close(self) -> None:
        """Close underlying client if it has a close method and we created it."""
        if self._owns_client and self._client is not None and hasattr(self._client, "aclose"):
            try:
                await self._client.aclose()
            except Exception:
                pass
        # Don't close provided client - caller owns it
        self._client = None
        self._provided_client = None
        self._owns_client = False


# ---------------------------------------------------------------------------
# Price formatting
# ---------------------------------------------------------------------------

def format_price_minor(minor: int, currency: str = "KZT") -> str:
    """Format minor units as human-readable price."""
    if currency == "KZT":
        major = minor // 100
        return f"{major:,} ₸".replace(",", " ")
    return f"{minor / 100:.2f} {currency}"