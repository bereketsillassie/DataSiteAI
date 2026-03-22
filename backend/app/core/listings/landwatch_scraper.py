"""
app/core/listings/landwatch_scraper.py
────────────────────────────────────────
LandWatch.com land listing scraper.

Rules:
  - Rate limit: 1 request per 2 seconds (hard requirement)
  - Respects robots.txt
  - Geocodes addresses via Nominatim (free, no key required)
  - Stores results in land_listings table with source="landwatch"

In MOCK mode: returns 5 realistic NC land listings without any HTTP calls.
"""

import asyncio
import logging
import re
from typing import Optional
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from app.config import settings as default_settings

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
LANDWATCH_BASE = "https://www.landwatch.com"


class LandWatchScraper:
    """Scrapes land listings from LandWatch.com."""

    def __init__(self, settings=None):
        self.settings = settings or default_settings
        self.mock = self.settings.MOCK_INTEGRATIONS
        self._http: Optional[httpx.AsyncClient] = None

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                headers={
                    "User-Agent": "DataCenter-Site-Selector/1.0 (contact@example.com)",
                    "Accept": "text/html,application/xhtml+xml",
                },
                follow_redirects=True,
            )
        return self._http

    async def close(self):
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    async def scrape_state(self, state: str, county: str = None, min_acres: float = 20.0) -> list[dict]:
        """
        Scrape land listings for a state (and optionally county).
        Returns list of listing dicts ready to insert into land_listings table.
        """
        if self.mock:
            return self._mock_listings(state)

        state_lower = state.lower()
        url = f"{LANDWATCH_BASE}/land-for-sale/{state_lower}"
        if county:
            county_lower = county.lower().replace(" ", "-")
            url = f"{url}/{county_lower}-county"

        # Check robots.txt compliance
        if not await self._check_robots():
            logger.warning("LandWatch robots.txt disallows scraping. Returning empty.")
            return []

        listings = []
        try:
            await asyncio.sleep(2.0)  # Hard rate limit: 1 request per 2 seconds
            client = await self._client()
            params = {
                "minAcres": int(min_acres),
                "propertyType": "commercial,industrial",
            }
            response = await client.get(url, params=params)
            response.raise_for_status()
            listings = self._parse_listings(response.text, state)
        except Exception as e:
            logger.error(f"LandWatch scrape failed for {state}: {e}")

        # Geocode any listings missing coordinates
        for listing in listings:
            if not listing.get("lat") and listing.get("address"):
                coords = await self._geocode(listing["address"])
                if coords:
                    listing["lat"] = coords[0]
                    listing["lng"] = coords[1]
                await asyncio.sleep(1.0)  # Nominatim rate limit: 1 req/sec

        return listings

    async def _check_robots(self) -> bool:
        """Returns True if scraping is allowed per robots.txt."""
        try:
            client = await self._client()
            resp = await client.get(f"{LANDWATCH_BASE}/robots.txt")
            content = resp.text.lower()
            # Look for disallow rules that would block us
            if "disallow: /land-for-sale" in content:
                return False
            return True
        except Exception:
            return True  # Allow if we can't fetch robots.txt

    def _parse_listings(self, html: str, state: str) -> list[dict]:
        """Parse HTML from LandWatch listing page."""
        listings = []
        soup = BeautifulSoup(html, "lxml")

        # LandWatch uses data-id attributes on listing cards
        cards = soup.find_all("div", {"class": re.compile(r"property-card|listing-card", re.I)})
        for card in cards[:50]:  # Max 50 listings per scrape
            try:
                listing = self._parse_card(card, state)
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.debug(f"Failed to parse card: {e}")
        return listings

    def _parse_card(self, card, state: str) -> Optional[dict]:
        """Parse a single listing card element."""
        # Extract price
        price_el = card.find(string=re.compile(r"\$[\d,]+"))
        price = None
        if price_el:
            price_str = re.sub(r"[^\d]", "", str(price_el))
            price = int(price_str) if price_str else None

        # Extract acreage
        acres_el = card.find(string=re.compile(r"[\d.]+ acres?", re.I))
        acres = None
        if acres_el:
            m = re.search(r"([\d.]+)\s+acres?", str(acres_el), re.I)
            acres = float(m.group(1)) if m else None

        # Extract address/location
        addr_el = card.find(["p", "span", "div"], {"class": re.compile(r"location|address|county", re.I)})
        address = addr_el.get_text(strip=True) if addr_el else None

        # Extract listing URL
        link = card.find("a", href=True)
        listing_url = LANDWATCH_BASE + link["href"] if link and link["href"].startswith("/") else None

        if not acres:
            return None

        price_per_acre = None
        if price and acres:
            price_per_acre = round(price / acres, 2)

        return {
            "source": "landwatch",
            "state": state.upper(),
            "address": address,
            "county": None,
            "acres": acres,
            "price_usd": price,
            "price_per_acre": price_per_acre,
            "lat": None,
            "lng": None,
            "listing_url": listing_url,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _geocode(self, address: str) -> Optional[tuple[float, float]]:
        """Geocode an address using Nominatim. Returns (lat, lng) or None."""
        try:
            client = await self._client()
            params = {
                "q": address + ", USA",
                "format": "json",
                "limit": 1,
                "countrycodes": "us",
            }
            headers = {"User-Agent": "DataCenter-Site-Selector/1.0 (contact@example.com)"}
            resp = await client.get(NOMINATIM_URL, params=params, headers=headers)
            data = resp.json()
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
        except Exception as e:
            logger.debug(f"Geocode failed for '{address}': {e}")
        return None

    def _mock_listings(self, state: str) -> list[dict]:
        """Return 5 realistic mock listings for NC."""
        now = datetime.now(timezone.utc).isoformat()
        return [
            {
                "source": "landwatch",
                "external_id": "lw_mock_001",
                "state": state.upper(),
                "county": "Wake",
                "address": "1234 Industrial Pkwy, Garner, NC 27529",
                "acres": 45.2,
                "price_usd": 380000,
                "price_per_acre": 8407.08,
                "lat": 35.707,
                "lng": -78.614,
                "listing_url": "https://www.landwatch.com/land-for-sale/nc/wake/mock-listing-001",
                "scraped_at": now,
            },
            {
                "source": "landwatch",
                "external_id": "lw_mock_002",
                "state": state.upper(),
                "county": "Johnston",
                "address": "Rural Route 55, Clayton, NC 27520",
                "acres": 82.7,
                "price_usd": 620000,
                "price_per_acre": 7497.58,
                "lat": 35.647,
                "lng": -78.455,
                "listing_url": "https://www.landwatch.com/land-for-sale/nc/johnston/mock-listing-002",
                "scraped_at": now,
            },
            {
                "source": "landwatch",
                "external_id": "lw_mock_003",
                "state": state.upper(),
                "county": "Chatham",
                "address": "Hwy 64 Bypass, Pittsboro, NC 27312",
                "acres": 120.0,
                "price_usd": 960000,
                "price_per_acre": 8000.0,
                "lat": 35.720,
                "lng": -79.175,
                "listing_url": "https://www.landwatch.com/land-for-sale/nc/chatham/mock-listing-003",
                "scraped_at": now,
            },
            {
                "source": "landwatch",
                "external_id": "lw_mock_004",
                "state": state.upper(),
                "county": "Franklin",
                "address": "Commerce Dr, Youngsville, NC 27596",
                "acres": 38.5,
                "price_usd": 295000,
                "price_per_acre": 7662.34,
                "lat": 36.034,
                "lng": -78.478,
                "listing_url": "https://www.landwatch.com/land-for-sale/nc/franklin/mock-listing-004",
                "scraped_at": now,
            },
            {
                "source": "landwatch",
                "external_id": "lw_mock_005",
                "state": state.upper(),
                "county": "Nash",
                "address": "Airport Rd, Rocky Mount, NC 27804",
                "acres": 65.3,
                "price_usd": 490000,
                "price_per_acre": 7504.59,
                "lat": 35.938,
                "lng": -77.796,
                "listing_url": "https://www.landwatch.com/land-for-sale/nc/nash/mock-listing-005",
                "scraped_at": now,
            },
        ]
