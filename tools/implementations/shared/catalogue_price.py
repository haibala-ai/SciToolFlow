"""Read public mass-package catalogue prices from the supplier's CAS page."""

from src.utils.paths import local_root, artifacts_root
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4

from bs4 import BeautifulSoup
import requests
from tools.implementations.shared.materials_api import MissingScientificData


def parse_public_mass_prices(html):
    soup = BeautifulSoup(html, "html.parser")
    quotes, seen = [], set()
    for table in soup.select(".related_pro_detail_right table"):
        headers = [cell.get_text(" ", strip=True) for cell in table.select("th")]
        if (
            not headers
            or "包装" not in headers
            or not any("目录价" in value for value in headers)
        ):
            continue
        package_index = headers.index("包装")
        price_index = next(
            index for index, value in enumerate(headers) if "目录价" in value
        )
        for row in table.select("tr"):
            cells = row.find_all("td", recursive=False)
            if len(cells) <= max(package_index, price_index):
                continue
            package = cells[package_index].get_text(" ", strip=True)
            match = re.fullmatch(
                r"\s*(\d+(?:\.\d+)?)\s*(kg|g|mg|ug|µg)\s*", package, re.I
            )
            if not match:
                continue
            text = cells[price_index].get_text(" ", strip=True)
            # The column is catalogue price / activity price; use its first
            # explicit public numeric price, never a login-only member column.
            price_match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(?:/.*)?", text, re.S)
            if not price_match:
                continue
            try:
                price = Decimal(price_match[1])
                grams = (
                    Decimal(match[1])
                    * {
                        "kg": Decimal(1000),
                        "g": Decimal(1),
                        "mg": Decimal("0.001"),
                        "ug": Decimal("0.000001"),
                        "µg": Decimal("0.000001"),
                    }[match[2].lower()]
                )
            except InvalidOperation:
                continue
            if (
                not price.is_finite()
                or not grams.is_finite()
                or grams <= 0
                or price <= 0
                or price in [99999, 999999]
            ):
                continue
            code = cells[0].get_text(" ", strip=True)
            key = (code, package, price)
            if key in seen:
                continue
            seen.add(key)
            quotes.append(
                {
                    "product_code": code,
                    "package": package,
                    "mass_g": float(grams),
                    "catalogue_price_CNY": float(price),
                    "catalogue_price_CNY_per_g": float(price / grams),
                }
            )
    if not quotes:
        raise MissingScientificData(
            "No explicit public catalogue prices for mass-only packages on this CAS page"
        )
    return quotes


def public_catalogue_price(cas):
    cas = cas.strip(" \"'")
    if not re.fullmatch(r"\d{2,7}-\d{2}-\d", cas):
        raise ValueError("Expected a CAS registry number")
    digits = cas.replace("-", "")
    if sum(
        index * int(digit) for index, digit in enumerate(reversed(digits[:-1]), 1)
    ) % 10 != int(digits[-1]):
        raise ValueError("CAS registry number checksum is invalid")
    url = f"https://www.energy-chemical.com/front/cas_{cas}.htm"
    with requests.Session() as session:
        session.trust_env = False
        response = session.get(url, timeout=25)
    if response.status_code == 404:
        raise MissingScientificData(
            f"The public supplier CAS page is unavailable for {cas}"
        )
    if not response.ok:
        raise RuntimeError(f"Supplier HTTP {response.status_code} at {url}")
    if f"cas_{cas}.htm" not in response.url:
        raise MissingScientificData(
            "Supplier redirected away from the requested CAS page"
        )
    quotes = parse_public_mass_prices(response.text)
    directory = artifacts_root() / f"catalogue_{uuid4().hex}"
    directory.mkdir(parents=True)
    artifact = directory / "public_catalogue.html"
    artifact.write_text(response.text)
    return json.dumps(
        {
            "cas": cas,
            "source_url": response.url,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "source_sha256": hashlib.sha256(response.content).hexdigest(),
            "source_artifact": str(artifact),
            "quotes": quotes,
            "valid_mass_packages": len(quotes),
            "mean_catalogue_CNY_per_g": sum(
                row["catalogue_price_CNY_per_g"] for row in quotes
            )
            / len(quotes),
            "scope": "Unweighted mean of public mass-package catalogue prices across listed products/grades. "
            "Volume and multipack packages are excluded; not a market-wide average or purchase quote.",
        },
        ensure_ascii=False,
    )
