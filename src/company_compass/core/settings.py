"""Environment configuration. Secret values are never included in diagnostics."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    app_mode: Literal["local", "cloud"] = "local"
    admin_token: SecretStr = SecretStr("")
    llm_provider: Literal["gemini"] = "gemini"
    llm_model: str = "gemini-3.8-flash"
    llm_api_key: SecretStr = SecretStr("")
    langfuse_secret_key: SecretStr = SecretStr("")
    langfuse_public_key: SecretStr = SecretStr("")
    langfuse_base_url: str = "https://cloud.langfuse.com"
    langfuse_enabled: bool = True
    langfuse_capture_content: bool = False
    langfuse_environment: str = "development"
    memory_token_limit: int = Field(default=6000, ge=500, le=100000)
    memory_keep_messages: int = Field(default=6, ge=2, le=40)
    agent_recursion_limit: int = Field(default=16, ge=4, le=50)
    gemini_use_vertexai: bool = True
    gemini_thinking_level: Literal["low", "medium", "high"] = "medium"
    google_cloud_project: str = ""
    google_cloud_location: str = "global"
    google_application_credentials: str = ""
    google_embedding_location: str = "us-central1"
    embedding_provider: Literal["weaviate", "vertex"] = "weaviate"
    embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = Field(default=1536, ge=1536, le=3072, strict=True)
    weaviate_vector_name: str = Field(default="google_1536", pattern=r"^[A-Za-z_]\w*$")
    neo4j_uri: str = ""
    neo4j_username: str = ""
    neo4j_password: SecretStr = SecretStr("")
    neo4j_database: str = "neo4j"
    weaviate_url: str = ""
    weaviate_api_key: SecretStr = SecretStr("")
    weaviate_collection: str = "CompanyChunk"
    company_domain: str = "attoforce.ai"
    neo4j_mcp_command: str = ""
    neo4j_mcp_args: list[str] = []
    catalog_path: Path = ROOT / "data/runtime/catalog.json"
    knowledge_path: Path = ROOT / "data/runtime/knowledge.json"

    @field_validator("embedding_dimensions", mode="before")
    @classmethod
    def parse_embedding_dimensions(cls, value):
        # Environment/subprocess configuration contains strings; retain strict
        # integer validation for booleans, floats and nonintegral strings.
        if isinstance(value, str) and value.strip().isascii() and value.strip().isdigit():
            return int(value.strip())
        return value

    @field_validator("weaviate_url")
    @classmethod
    def normalize_cloud_url(cls, value: str) -> str:
        if value and not value.startswith("https://"):
            return "https://" + value
        return value

    @property
    def admin_configured(self) -> bool:
        return bool(self.admin_token.get_secret_value())

    @property
    def model_configured(self) -> bool:
        if self.llm_provider == "gemini" and self.gemini_use_vertexai:
            # Credentials may come from an explicit service account or ambient ADC.
            # Configuration inspection must not perform authentication or network calls.
            return bool(self.llm_model and self.google_cloud_project)
        return bool(self.llm_model and self.llm_api_key.get_secret_value())
