import pytest

from company_compass.repositories.catalog import LocalCatalogRepository
from company_compass.utils import storage
from company_compass.utils.seed import load_demo_products


def test_local_publication_retries_transient_windows_file_locks(tmp_path, monkeypatch):
    original_replace = storage.os.replace
    attempts = 0

    def briefly_locked(source, destination):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError("Temporary file lock")
        return original_replace(source, destination)

    monkeypatch.setattr(storage.os, "replace", briefly_locked)
    repository = LocalCatalogRepository(tmp_path / "catalog.json")
    product = repository.publish(load_demo_products()[0], None)
    assert repository.get_product(product.id).revision == 1
    assert attempts == 3


def test_failed_atomic_replacement_preserves_previous_publication(tmp_path, monkeypatch):
    repository = LocalCatalogRepository(tmp_path / "catalog.json")
    product = repository.publish(load_demo_products()[0], None)
    attempts = 0

    def always_locked(source, destination):
        nonlocal attempts
        attempts += 1
        raise PermissionError("Persistent file lock")

    monkeypatch.setattr(storage.os, "replace", always_locked)
    with pytest.raises(PermissionError):
        repository.publish(product.model_copy(update={"name": "Unpublished"}), 1)
    assert attempts == 5
    assert repository.get_product(product.id).name == product.name
    assert list(tmp_path.iterdir()) == [tmp_path / "catalog.json"]


def test_atomic_write_does_not_retry_other_filesystem_failures(tmp_path, monkeypatch):
    calls = 0

    def disk_failed(source, destination):
        nonlocal calls
        calls += 1
        raise OSError("Disk failure")

    monkeypatch.setattr(storage.os, "replace", disk_failed)
    with pytest.raises(OSError, match="Disk failure"):
        storage.atomic_write_json(tmp_path / "catalog.json", {"ready": True})
    assert calls == 1
    assert list(tmp_path.iterdir()) == []
