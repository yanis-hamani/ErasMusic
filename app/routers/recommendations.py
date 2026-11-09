from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query

from app.dependencies import verify_access_token
from app.models.recommendations import (
    PaginatedArtistGroupRecommendations,
    PaginatedArtistUserRecommendations,
    PaginatedFriendGroupRecommendations,
    PaginatedFriendUserRecommendations,
    PaginatedGenreGroupRecommendations,
    PaginatedSongUserRecommendations,
    RecommendationPeriod,
)
from app.services.recommendation_services import RecommendationService


router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get(
    "/friends/by-artists",
    response_model=PaginatedArtistUserRecommendations,
    responses={
        401: {"description": "Unauthorized"},
        422: {"description": "Unprocessable Entity"},
    },
)
@inject
async def recommend_friends_by_artists(
    recommendation_service: FromDishka[RecommendationService],
    period: RecommendationPeriod = Query(...),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    user_id: str = Depends(verify_access_token),
) -> PaginatedArtistUserRecommendations:
    return await recommendation_service.recommend_friends_by_artists(
        user_id,
        period,
        page,
        limit,
    )


@router.get(
    "/friends/by-songs",
    response_model=PaginatedSongUserRecommendations,
    responses={
        401: {"description": "Unauthorized"},
        422: {"description": "Unprocessable Entity"},
    },
)
@inject
async def recommend_friends_by_songs(
    recommendation_service: FromDishka[RecommendationService],
    period: RecommendationPeriod = Query(...),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    user_id: str = Depends(verify_access_token),
) -> PaginatedSongUserRecommendations:
    return await recommendation_service.recommend_friends_by_songs(
        user_id,
        period,
        page,
        limit,
    )


@router.get(
    "/friends/by-friends",
    response_model=PaginatedFriendUserRecommendations,
    responses={
        401: {"description": "Unauthorized"},
        422: {"description": "Unprocessable Entity"},
    },
)
@inject
async def recommend_friends_by_friends(
    recommendation_service: FromDishka[RecommendationService],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    user_id: str = Depends(verify_access_token),
) -> PaginatedFriendUserRecommendations:
    return await recommendation_service.recommend_friends_by_friends(
        user_id,
        page,
        limit,
    )


@router.get(
    "/groups/by-artists",
    response_model=PaginatedArtistGroupRecommendations,
    responses={
        401: {"description": "Unauthorized"},
        422: {"description": "Unprocessable Entity"},
    },
)
@inject
async def recommend_groups_by_artists(
    recommendation_service: FromDishka[RecommendationService],
    period: RecommendationPeriod = Query(...),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    user_id: str = Depends(verify_access_token),
) -> PaginatedArtistGroupRecommendations:
    return await recommendation_service.recommend_groups_by_artists(
        user_id,
        period,
        page,
        limit,
    )


@router.get(
    "/groups/by-genres",
    response_model=PaginatedGenreGroupRecommendations,
    responses={
        401: {"description": "Unauthorized"},
        422: {"description": "Unprocessable Entity"},
    },
)
@inject
async def recommend_groups_by_genres(
    recommendation_service: FromDishka[RecommendationService],
    period: RecommendationPeriod = Query(...),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    user_id: str = Depends(verify_access_token),
) -> PaginatedGenreGroupRecommendations:
    return await recommendation_service.recommend_groups_by_genres(
        user_id,
        period,
        page,
        limit,
    )


@router.get(
    "/groups/by-friends",
    response_model=PaginatedFriendGroupRecommendations,
    responses={
        401: {"description": "Unauthorized"},
        422: {"description": "Unprocessable Entity"},
    },
)
@inject
async def recommend_groups_by_friends(
    recommendation_service: FromDishka[RecommendationService],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    user_id: str = Depends(verify_access_token),
) -> PaginatedFriendGroupRecommendations:
    return await recommendation_service.recommend_groups_by_friends(
        user_id,
        page,
        limit,
    )
