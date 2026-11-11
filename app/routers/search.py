from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query

from app.core.openapi import (
    LIMIT_DESCRIPTION,
    PAGE_DESCRIPTION,
    SEARCH_DESCRIPTION,
    UNAUTHORIZED_RESPONSE,
    VALIDATION_RESPONSE,
)
from app.dependencies import verify_access_token
from app.models.groups import PaginatedGroupsResponse
from app.models.search import PaginatedUsersResponse
from app.services.search_services import SearchService


router = APIRouter(prefix="/search", tags=["Search"])


@router.get(
    "/users",
    response_model=PaginatedUsersResponse,
    operation_id="searchUsers",
    summary="Search people",
    description=(
        "Searches usernames using case-insensitive literal substring matching. "
        "The authenticated user is excluded. Exact matches are returned first, "
        "followed by prefix and substring matches, with deterministic "
        "alphabetical ordering within each relevance level."
    ),
    response_description="Matching users retrieved successfully",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        422: VALIDATION_RESPONSE,
    },
)
@inject
async def search_users(
    search_service: FromDishka[SearchService],
    q: str = Query(..., min_length=1, pattern=r"\S", description=SEARCH_DESCRIPTION),
    page: int = Query(default=1, ge=1, description=PAGE_DESCRIPTION),
    limit: int = Query(default=10, ge=1, le=100, description=LIMIT_DESCRIPTION),
    user_id: str = Depends(verify_access_token),
) -> PaginatedUsersResponse:
    return await search_service.search_users(user_id, q, page, limit)


@router.get(
    "/groups",
    response_model=PaginatedGroupsResponse,
    operation_id="searchGroups",
    summary="Search groups",
    description=(
        "Searches group names, descriptions, artist tags, and genre tags using "
        "case-insensitive literal substring matching. Exact matches are returned "
        "first, followed by prefix and substring matches, with deterministic "
        "alphabetical ordering within each relevance level."
    ),
    response_description="Matching groups retrieved successfully",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        422: VALIDATION_RESPONSE,
    },
)
@inject
async def search_groups(
    search_service: FromDishka[SearchService],
    q: str = Query(..., min_length=1, pattern=r"\S", description=SEARCH_DESCRIPTION),
    page: int = Query(default=1, ge=1, description=PAGE_DESCRIPTION),
    limit: int = Query(default=10, ge=1, le=100, description=LIMIT_DESCRIPTION),
    _user_id: str = Depends(verify_access_token),
) -> PaginatedGroupsResponse:
    return await search_service.search_groups(q, page, limit)
