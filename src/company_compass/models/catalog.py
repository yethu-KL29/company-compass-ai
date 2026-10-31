"""Public catalog contracts. Prices use integer minor units, never floats."""

import math
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

ATTRIBUTE_DEFINITIONS = {
    "deployment_mode": {
        "data_type": "text",
        "canonical_unit": "mode",
        "comparison_rule": "equal",
        "allowed_values": ["cloud", "self_hosted", "hybrid"],
    },
    "support_level": {
        "data_type": "text",
        "canonical_unit": "tier",
        "comparison_rule": "equal",
        "allowed_values": ["community", "standard", "premium", "enterprise"],
    },
    "included_documents_per_month": {
        "data_type": "integer",
        "canonical_unit": "documents/month",
        "comparison_rule": "higher",
    },
    "automation_rules": {
        "data_type": "integer",
        "canonical_unit": "rules",
        "comparison_rule": "higher",
    },
    "contacts": {"data_type": "integer", "canonical_unit": "contacts", "comparison_rule": "higher"},
    "storage_gb": {"data_type": "number", "canonical_unit": "GB", "comparison_rule": "higher"},
}


class CatalogModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Plan(CatalogModel):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=150)
    capabilities: list[str] = Field(default_factory=list, max_length=100)
    use_cases: list[str] = Field(default_factory=list, max_length=30)
    audiences: list[str] = Field(default_factory=list, max_length=30)
    max_users: int | None = Field(default=None, ge=1)
    price_minor: int | None = Field(default=None, ge=0)
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    billing_period: Literal["month", "year", "once"] = "month"
    billing_unit: Literal["organization", "seat"] = "organization"
    attributes: dict[str, StrictStr | StrictInt | StrictFloat | StrictBool] = Field(
        default_factory=dict, max_length=50
    )
    upgrades_to: list[str] = Field(default_factory=list)

    @field_validator("attributes")
    @classmethod
    def validate_attributes(cls, attributes):
        for code, value in attributes.items():
            definition = ATTRIBUTE_DEFINITIONS.get(code)
            if definition is None:
                raise ValueError(f"Unknown specification code: {code}")
            kind = definition["data_type"]
            if kind == "text":
                if type(value) is not str or value not in definition["allowed_values"]:
                    raise ValueError(f"Invalid value for {code}")
            elif kind == "integer":
                if type(value) is not int or value < 0:
                    raise ValueError(f"{code} must be a nonnegative integer")
            elif type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{code} must be a finite nonnegative number")
        return attributes

    @field_validator("capabilities", "use_cases", "audiences")
    @classmethod
    def normalized_terms(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("Catalog terms cannot be empty")
        return list(dict.fromkeys(value.strip().lower() for value in values))


class Product(CatalogModel):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=150)
    description: str = Field(min_length=1, max_length=5000)
    categories: list[str] = Field(min_length=1, max_length=20)
    use_cases: list[str] = Field(default_factory=list)
    audiences: list[str] = Field(default_factory=list)
    plans: list[Plan] = Field(min_length=1, max_length=20)
    complements: list[str] = Field(default_factory=list)
    is_synthetic: Literal[True] = True
    revision: int = Field(default=1, ge=1)
    status: Literal["active", "retired"] = "active"

    @field_validator("categories", "use_cases", "audiences")
    @classmethod
    def normalized_terms(cls, values: list[str]) -> list[str]:
        return Plan.normalized_terms(values)

    @model_validator(mode="after")
    def unique_plans(self):
        ids = [plan.id for plan in self.plans]
        if len(ids) != len(set(ids)):
            raise ValueError("Plan IDs must be unique within a product")
        for plan in self.plans:
            if any(target not in ids or target == plan.id for target in plan.upgrades_to):
                raise ValueError("Upgrade targets must be another plan in the product")
        return self
