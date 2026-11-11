from typing import Literal

from pydantic import BaseModel, Field


class HTTPError(BaseModel):
    detail: str = Field(
        ...,
        description="Human-readable error message",
        example="Not found",
    )


class ValidationError(BaseModel):
    loc: list[str | int] = Field(
        ...,
        description="Location of the invalid value",
        example=["body", "email"],
    )
    msg: str = Field(
        ...,
        description="Human-readable validation message",
        example="Field required",
    )
    type: str = Field(
        ...,
        description="Validation error identifier",
        example="missing",
    )


class HTTPValidationError(BaseModel):
    detail: list[ValidationError]


class DatabaseHealth(BaseModel):
    neo4j: Literal["connected"] = Field(..., example="connected")
    postgres: Literal["connected"] = Field(..., example="connected")


class HealthResponse(BaseModel):
    status: Literal["ok"] = Field(..., example="ok")
    databases: DatabaseHealth


class Pagination(BaseModel):
    """Pagination metadata."""

    page: int = Field(..., ge=1, description="Current page number", example=1)
    limit: int = Field(
        ...,
        ge=1,
        le=100,
        description="Maximum number of items per page",
        example=10,
    )
    totalItems: int = Field(
        ...,
        ge=0,
        description="Total number of items available",
        example=42,
    )
    totalPages: int = Field(
        ...,
        ge=0,
        description="Total number of pages available",
        example=5,
    )
