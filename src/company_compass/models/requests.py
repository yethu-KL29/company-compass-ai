"""HTTP request contracts; business rules remain in services."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from company_compass.models.catalog import Product


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChatRequest(RequestModel):
    message: str = Field(min_length=1, max_length=2000)
    thread_id: UUID | None = None


class PublishRequest(RequestModel):
    product: Product
    expected_revision: int | None = Field(default=None, ge=1)


class IngestRequest(RequestModel):
    urls: list[str] = Field(min_length=1, max_length=10)


class DocumentReplacement(RequestModel):
    title: str = Field(min_length=1, max_length=250)
    content: str = Field(min_length=1, max_length=2_000_000)
    expected_revision: int = Field(ge=1)

    @field_validator("title")
    @classmethod
    def title_is_readable(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter a document title")
        return value.strip()

    @field_validator("content")
    @classmethod
    def content_is_readable(cls, value: str) -> str:
        if not value.strip() or len(value.encode("utf-8")) > 2_000_000:
            raise ValueError("Enter document content of at most 2 MB")
        return value
