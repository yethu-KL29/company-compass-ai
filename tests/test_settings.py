from pydantic import SecretStr

from company_compass.core.settings import Settings


def test_secrets_are_redacted_and_url_is_normalized():
    settings = Settings(
        _env_file=None,
        weaviate_url="example.weaviate.cloud",
        weaviate_api_key="private-value",
        neo4j_password="another-secret",
    )
    assert settings.weaviate_url == "https://example.weaviate.cloud"
    assert "private-value" not in repr(settings)
    assert "another-secret" not in repr(settings)


def test_admin_token_must_be_explicit():
    settings = Settings(_env_file=None, admin_token="")
    assert not settings.admin_configured


def test_gemini_defaults_use_vertex_medium_without_embedded_credentials():
    settings = Settings(_env_file=None, google_cloud_project="", llm_api_key="")
    assert settings.llm_provider == "gemini"
    assert settings.llm_model == "gemini-3.8-flash"
    assert settings.gemini_use_vertexai is True
    assert settings.gemini_thinking_level == "medium"
    assert not settings.model_configured


def test_vertex_configuration_can_use_adc_without_api_key():
    settings = Settings(
        _env_file=None,
        llm_provider="gemini",
        llm_model="gemini-3.8-flash",
        gemini_use_vertexai=True,
        google_cloud_project="assignment-project",
        llm_api_key="",
    )
    assert settings.model_configured


def test_api_key_modes_still_require_a_key():
    settings = Settings(
        _env_file=None,
        llm_provider="gemini",
        gemini_use_vertexai=False,
        llm_api_key="",
    )
    assert not settings.model_configured
    assert settings.model_copy(update={"llm_api_key": SecretStr("key")}).model_configured


def test_embedding_defaults_preserve_existing_provider_until_migration():
    settings = Settings(_env_file=None)
    assert settings.embedding_provider == "weaviate"
    assert settings.embedding_model == "gemini-embedding-001"
    assert settings.embedding_dimensions == 1536
    assert settings.weaviate_vector_name == "google_1536"
    assert settings.google_embedding_location == "us-central1"


def test_embedding_dimensions_respect_assignment_minimum():
    import pytest
    from pydantic import ValidationError

    for dimensions in (768, 3073, True):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, embedding_dimensions=dimensions)


def test_embedding_dimensions_accept_integer_environment_values(monkeypatch):
    monkeypatch.setenv("EMBEDDING_DIMENSIONS", "1536")
    assert Settings(_env_file=None).embedding_dimensions == 1536


def test_embedding_dimensions_reject_nonintegral_environment_values(monkeypatch):
    import pytest
    from pydantic import ValidationError

    for value in ("1536.5", "true", "1536.0", "768", "3073"):
        monkeypatch.setenv("EMBEDDING_DIMENSIONS", value)
        with pytest.raises(ValidationError):
            Settings(_env_file=None)
