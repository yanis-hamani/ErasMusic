from pydantic import BaseModel, Field

from app.models.common import Pagination


class SearchUser(BaseModel):
    id: str = Field(
        ...,
        description="Unique user identifier",
        example="usr_a1b2c3d4e5f6",
    )
    username: str = Field(..., description="User name", example="alex")


class PaginatedUsersResponse(BaseModel):
    users: list[SearchUser]
    pagination: Pagination
