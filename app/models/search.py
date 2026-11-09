from pydantic import BaseModel, Field

from app.models.common import Pagination


class SearchUser(BaseModel):
    id: str = Field(..., description="Unique user identifier")
    username: str = Field(..., description="User name")


class PaginatedUsersResponse(BaseModel):
    users: list[SearchUser]
    pagination: Pagination
