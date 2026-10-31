from pathlib import Path

import pytest
from pydantic import ValidationError

from company_compass.models.catalog import Plan, Product
from company_compass.repositories.catalog import LocalCatalogRepository, RevisionConflict
from company_compass.services.catalog import CatalogService
from company_compass.utils.seed import load_demo_products


@pytest.fixture
def catalog(tmp_path: Path) -> CatalogService:
    service = CatalogService(LocalCatalogRepository(tmp_path / "catalog.json"))
    for product in load_demo_products():
        service.publish(product, expected_revision=None)
    return service


def test_publish_is_persistent_and_rejects_stale_edits(tmp_path):
    path = tmp_path / "catalog.json"
    service = CatalogService(LocalCatalogRepository(path))
    original = load_demo_products()[0]
    created = service.publish(original, None)
    changed = created.model_copy(update={"name": "Updated"})
    updated = service.publish(changed, created.revision)
    assert updated.revision == 2
    assert CatalogService(LocalCatalogRepository(path)).get_product(original.id).name == "Updated"
    with pytest.raises(RevisionConflict):
        service.publish(changed, created.revision)


def test_retired_products_are_not_visible(catalog):
    product = catalog.get_product("salesflow")
    catalog.publish(product.model_copy(update={"status": "retired"}), product.revision)
    assert catalog.get_product("salesflow") is None
    assert all(product.id != "salesflow" for product in catalog.list_products())


def test_invalid_price_and_duplicate_plan_are_rejected():
    with pytest.raises(ValidationError):
        Plan(id="bad", name="Bad", price_minor=-1)
    with pytest.raises(ValidationError):
        Product(
            id="test",
            name="Test",
            description="Demo",
            categories=["crm"],
            plans=[Plan(id="same", name="One"), Plan(id="same", name="Two")],
        )


@pytest.mark.parametrize(
    "attributes",
    [
        {"invented_spec": 1},
        {"included_documents_per_month": "many"},
        {"automation_rules": -1},
        {"contacts": True},
        {"deployment_mode": "magic"},
    ],
)
def test_fixed_attribute_registry_rejects_unknown_codes_and_invalid_values(attributes):
    with pytest.raises(ValidationError):
        Plan(id="base", name="Base", attributes=attributes)


@pytest.mark.parametrize("field", ["categories", "use_cases", "audiences"])
def test_product_terms_reject_empty_strings(field):
    values = {
        "id": "bad",
        "name": "Bad",
        "description": "Synthetic",
        "categories": ["crm"],
        "plans": [Plan(id="base", name="Base")],
    }
    values[field] = ["   "]
    with pytest.raises(ValidationError, match="empty"):
        Product(**values)
