from unittest.mock import Mock, sentinel

import pytest

from company_compass.core.settings import Settings
from company_compass.integrations.chat_model import create_chat_model


def test_vertex_model_preserves_native_streaming_and_medium_reasoning(monkeypatch):
    import langchain_google_genai
    from google.oauth2 import service_account

    constructor = Mock(return_value=sentinel.model)
    credentials = Mock(return_value=sentinel.credentials)
    monkeypatch.setattr(langchain_google_genai, "ChatGoogleGenerativeAI", constructor)
    monkeypatch.setattr(service_account.Credentials, "from_service_account_file", credentials)
    settings = Settings(
        _env_file=None,
        google_cloud_project="test-project",
        google_application_credentials="service-account.json",
    )
    assert create_chat_model(settings) is sentinel.model
    credentials.assert_called_once_with(
        "service-account.json", scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    options = constructor.call_args.kwargs
    assert options["model"] == "gemini-3.8-flash"
    assert options["thinking_level"] == "medium"
    assert options["include_thoughts"] is False
    assert options["streaming"] is True
    assert options["vertexai"] is True
    assert options["project"] == "test-project"
    assert options["location"] == "global"
    assert options["credentials"] is sentinel.credentials
    assert "api_key" not in options


def test_vertex_adc_does_not_load_explicit_credentials(monkeypatch):
    import langchain_google_genai
    from google.oauth2 import service_account

    constructor = Mock()
    credentials = Mock()
    monkeypatch.setattr(langchain_google_genai, "ChatGoogleGenerativeAI", constructor)
    monkeypatch.setattr(service_account.Credentials, "from_service_account_file", credentials)
    create_chat_model(Settings(_env_file=None, google_cloud_project="test-project"))
    credentials.assert_not_called()
    assert "credentials" not in constructor.call_args.kwargs


def test_api_key_mode_keeps_explicit_authentication(monkeypatch):
    import langchain_google_genai

    constructor = Mock()
    monkeypatch.setattr(langchain_google_genai, "ChatGoogleGenerativeAI", constructor)
    create_chat_model(Settings(_env_file=None, gemini_use_vertexai=False, llm_api_key="test-key"))
    assert constructor.call_args.kwargs["vertexai"] is False
    assert constructor.call_args.kwargs["api_key"] == "test-key"


def test_missing_model_configuration_is_clear():
    with pytest.raises(ValueError, match="Configure Gemini"):
        create_chat_model(Settings(_env_file=None))
