from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query

from app.dependencies import verify_access_token
from app.models.groups import PaginatedGroupsResponse
from app.models.search import PaginatedUsersResponse
from app.services.search_services import SearchService


router = APIRouter(prefix="/search", tags=["Search"])


@router.get(
    "/users",
    response_model=PaginatedUsersResponse,
    responses={
        401: {"description": "Unauthorized"},
        422: {"description": "Unprocessable Entity"},
    },
)
@inject
async def search_users(
    search_service: FromDishka[SearchService],
    q: str = Query(..., min_length=1, pattern=r"\S"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    user_id: str = Depends(verify_access_token),
) -> PaginatedUsersResponse:
    return await search_service.search_users(user_id, q, page, limit)


@router.get(
    "/groups",
    response_model=PaginatedGroupsResponse,
    responses={
        401: {"description": "Unauthorized"},
        422: {"description": "Unprocessable Entity"},
    },
)
@inject
async def search_groups(
    search_service: FromDishka[SearchService],
    q: str = Query(..., min_length=1, pattern=r"\S"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    _user_id: str = Depends(verify_access_token),
) -> PaginatedGroupsResponse:
    return await search_service.search_groups(q, page, limit)
