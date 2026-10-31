"""Published product administration; chat reads the graph through Neo4j MCP."""

from company_compass.models.catalog import Product


class CatalogService:
    def __init__(self, repository):
        self.repository = repository

    def list_products(self) -> list[Product]:
        return [
            product for product in self.repository.list_products() if product.status == "active"
        ]

    def get_product(self, product_id: str) -> Product | None:
        product = self.repository.get_product(product_id)
        return product if product and product.status == "active" else None

    def publish(self, product: Product, expected_revision: int | None = None) -> Product:
        validated = Product.model_validate(product.model_dump())
        return self.repository.publish(validated, expected_revision)
