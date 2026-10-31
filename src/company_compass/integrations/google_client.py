"""Lazy Google SDK authentication shared by chat and embedding adapters."""

from company_compass.core.settings import Settings


def create_google_client(
    settings: Settings, *, vertexai: bool | None = None, location: str | None = None
):
    from google import genai
    from google.genai import types

    use_vertexai = settings.gemini_use_vertexai if vertexai is None else vertexai
    options = {"http_options": types.HttpOptions(timeout=45000)}
    if use_vertexai:
        if not settings.google_cloud_project:
            raise ValueError("Configure a Google Cloud project before using Vertex AI")
        options.update(
            vertexai=True,
            project=settings.google_cloud_project,
            location=location or settings.google_cloud_location,
        )
        if settings.google_application_credentials:
            from google.oauth2 import service_account

            options["credentials"] = service_account.Credentials.from_service_account_file(
                settings.google_application_credentials,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
    else:
        if not settings.llm_api_key.get_secret_value():
            raise ValueError("Configure a Gemini API key before using API-key authentication")
        options["api_key"] = settings.llm_api_key.get_secret_value()
    return genai.Client(**options)
