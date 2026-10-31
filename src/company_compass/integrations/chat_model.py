"""Native Gemini chat model; LangChain preserves streaming and tool signatures."""

from company_compass.core.settings import Settings


def create_chat_model(settings: Settings):
    """Create a tool-capable model without making an inference request."""
    if settings.llm_provider != "gemini" or not settings.model_configured:
        raise ValueError("Configure Gemini and its authentication before using the assistant")

    from langchain_google_genai import ChatGoogleGenerativeAI

    options = {
        "model": settings.llm_model,
        "vertexai": settings.gemini_use_vertexai,
        "thinking_level": settings.gemini_thinking_level,
        "include_thoughts": False,
        "streaming": True,
        "timeout": 45,
        "max_retries": 1,
    }
    if settings.gemini_use_vertexai:
        options.update(
            project=settings.google_cloud_project, location=settings.google_cloud_location
        )
        if settings.google_application_credentials:
            from google.oauth2 import service_account

            options["credentials"] = service_account.Credentials.from_service_account_file(
                settings.google_application_credentials,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
    else:
        options["api_key"] = settings.llm_api_key.get_secret_value()
    return ChatGoogleGenerativeAI(**options)
