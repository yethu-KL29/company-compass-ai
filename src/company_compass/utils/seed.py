"""Load fictional assignment data without silently changing cloud databases."""

import json
from pathlib import Path

from company_compass.models.catalog import Product


def load_demo_products(path: Path | None = None) -> list[Product]:
    source = path or Path(__file__).resolve().parents[3] / "data" / "demo-products.json"
    return [Product.model_validate(item) for item in json.loads(source.read_text(encoding="utf-8"))]
