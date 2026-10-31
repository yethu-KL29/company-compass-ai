from fastapi.testclient import TestClient

from company_compass.core.settings import Settings
from company_compass.main import create_app


def client(tmp_path):
    settings = Settings(
        _env_file=None,
        app_mode="local",
        admin_token="test-admin",
        catalog_path=tmp_path / "catalog.json",
        knowledge_path=tmp_path / "knowledge.json",
    )
    return TestClient(create_app(settings))


def test_admin_schema_requires_authentication(tmp_path):
    with client(tmp_path) as api:
        assert api.get("/api/admin/schema").status_code == 401
        response = api.get("/api/admin/schema", headers={"X-Admin-Token": "test-admin"})
        assert response.status_code == 200
        assert response.json()["schema_version"] == "assignment-v1"


def test_unseeded_catalog_is_explicitly_empty_and_unknown_product_404(tmp_path):
    with client(tmp_path) as api:
        assert api.get("/api/products").json() == []
        assert api.get("/api/products/missing").status_code == 404
        assert (
            api.post("/api/products/compare", json={"product_ids": ["a", "b"]}).status_code == 405
        )


def test_health_does_not_include_credentials(tmp_path):
    with client(tmp_path) as api:
        response = api.get("/api/health")
        assert response.status_code == 200
        assert "test-admin" not in response.text
        assert response.json()["mode"] == "local"


def test_admin_publication_is_protected_and_rejects_stale_edits(tmp_path):
    from company_compass.utils.seed import load_demo_products

    payload = {"product": load_demo_products()[0].model_dump(), "expected_revision": None}
    headers = {"X-Admin-Token": "test-admin"}
    with client(tmp_path) as api:
        assert api.post("/api/admin/products", json=payload).status_code == 401
        published = api.post("/api/admin/products", json=payload, headers=headers)
        assert published.status_code == 200
        assert published.json()["revision"] == 1
        assert api.post("/api/admin/products", json=payload, headers=headers).status_code == 409
        assert len(api.get("/api/products").json()) == 1
