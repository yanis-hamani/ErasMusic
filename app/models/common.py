from pydantic import BaseModel, Field


class Pagination(BaseModel):
    page: int = Field(..., ge=1, description="Current page number", example=1)
    limit: int = Field(..., ge=1, description="Maximum items per page", example=10)
    totalItems: int = Field(..., ge=0, description="Total available items", example=42)
    totalPages: int = Field(..., ge=0, description="Total available pages", example=5)
