"""Published product reads and authenticated catalog publication."""

from fastapi import APIRouter, Depends, HTTPException

from company_compass.api.dependencies import CatalogDependency, require_admin
from company_compass.models.catalog import Product
from company_compass.models.requests import PublishRequest

router = APIRouter(prefix="/api", tags=["products"])


@router.get("/products")
def products(catalog: CatalogDependency) -> list[Product]:
    return catalog.list_products()


@router.get("/products/{product_id}")
def product(product_id: str, catalog: CatalogDependency) -> Product:
    result = catalog.get_product(product_id)
    if not result:
        raise HTTPException(status_code=404, detail="Published product not found")
    return result


@router.post("/admin/products", dependencies=[Depends(require_admin)])
def publish(request: PublishRequest, catalog: CatalogDependency) -> Product:
    return catalog.publish(request.product, request.expected_revision)
