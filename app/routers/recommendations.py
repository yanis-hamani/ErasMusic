from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query

from app.core.openapi import (
    PAGE_DESCRIPTION,
    PERIOD_DESCRIPTION,
    UNAUTHORIZED_RESPONSE,
    VALIDATION_RESPONSE,
)
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
    operation_id="recommendFriendsByArtists",
    summary="Recommend users based on artists you listen to",
    description=(
        "Returns users who have also listened to artists you listened to during "
        "the selected time period, grouped by artist. Artist groups are ordered "
        "by your summed period score, and users within each group are ordered by "
        "their summed score for that artist. The authenticated user, existing "
        "friends, and zero-score activity are excluded. Each artist can have up "
        "to 20 recommended users."
    ),
    response_description="Recommended users grouped by artist",
    responses={401: UNAUTHORIZED_RESPONSE, 422: VALIDATION_RESPONSE},
)
@inject
async def recommend_friends_by_artists(
    recommendation_service: FromDishka[RecommendationService],
    period: RecommendationPeriod = Query(..., description=PERIOD_DESCRIPTION),
    page: int = Query(default=1, ge=1, description=PAGE_DESCRIPTION),
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Maximum artists to return",
    ),
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
    operation_id="recommendFriendsBySongs",
    summary="Recommend users based on songs you listen to",
    description=(
        "Returns users who listened to the same songs during the selected time "
        "period, grouped by song. Song groups are ordered by your period score, "
        "and users within each group are ordered by their score for that song. "
        "The authenticated user, existing friends, and zero-score activity are "
        "excluded. Each song can have up to 20 recommended users."
    ),
    response_description="Recommended users grouped by song",
    responses={401: UNAUTHORIZED_RESPONSE, 422: VALIDATION_RESPONSE},
)
@inject
async def recommend_friends_by_songs(
    recommendation_service: FromDishka[RecommendationService],
    period: RecommendationPeriod = Query(..., description=PERIOD_DESCRIPTION),
    page: int = Query(default=1, ge=1, description=PAGE_DESCRIPTION),
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Maximum songs to return",
    ),
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
    operation_id="recommendFriendsByFriends",
    summary="Recommend users through your closest friends",
    description=(
        "Returns users who are not yet your friends but share at least one mutual "
        "friend with you. Recommendations are grouped by mutual friend and "
        "prioritized using lazily decayed friendship closeness. Mutual-friend "
        "groups are ordered by your effective closeness to that friend. Users "
        "within each group are ordered by the product of both effective closeness "
        "values along the two-edge path. A user may appear under multiple mutual "
        "friends. Each mutual friend can have up to 20 recommended users."
    ),
    response_description=(
        "Recommended users grouped by mutual friend and ordered by closeness"
    ),
    responses={401: UNAUTHORIZED_RESPONSE, 422: VALIDATION_RESPONSE},
)
@inject
async def recommend_friends_by_friends(
    recommendation_service: FromDishka[RecommendationService],
    page: int = Query(default=1, ge=1, description=PAGE_DESCRIPTION),
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of mutual-friend groups to return per page",
    ),
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
    operation_id="recommendGroupsByArtists",
    summary="Recommend groups based on artists you listen to",
    description=(
        "Returns groups tagged with artists you listened to during the selected "
        "time period. Artist groups are ordered by your summed period score. "
        "Groups you already joined and zero-score activity are excluded. Groups "
        "within each artist are ordered by name and ID, with at most 20 groups "
        "per artist."
    ),
    response_description="Recommended groups grouped by artist",
    responses={401: UNAUTHORIZED_RESPONSE, 422: VALIDATION_RESPONSE},
)
@inject
async def recommend_groups_by_artists(
    recommendation_service: FromDishka[RecommendationService],
    period: RecommendationPeriod = Query(..., description=PERIOD_DESCRIPTION),
    page: int = Query(default=1, ge=1, description=PAGE_DESCRIPTION),
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Maximum artists to return",
    ),
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
    operation_id="recommendGroupsByGenres",
    summary="Recommend groups based on genres you listen to",
    description=(
        "Returns groups tagged with genres related to songs you listened to "
        "during the selected time period. Genre groups are ordered by your summed "
        "period score. Groups you already joined and zero-score activity are "
        "excluded. Groups within each genre are ordered by name and ID, with at "
        "most 20 groups per genre."
    ),
    response_description="Recommended groups grouped by genre",
    responses={401: UNAUTHORIZED_RESPONSE, 422: VALIDATION_RESPONSE},
)
@inject
async def recommend_groups_by_genres(
    recommendation_service: FromDishka[RecommendationService],
    period: RecommendationPeriod = Query(..., description=PERIOD_DESCRIPTION),
    page: int = Query(default=1, ge=1, description=PAGE_DESCRIPTION),
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of genres to return",
    ),
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
    operation_id="recommendGroupsByFriends",
    summary="Recommend groups through your closest friends",
    description=(
        "Returns groups that include your friends but that you have not joined. "
        "Recommendations are grouped by friend and ordered by lazily decayed "
        "effective relationship closeness. Groups within each friend are ordered "
        "by name and ID. A group may appear under multiple friends, and each "
        "friend can have up to 20 recommended groups."
    ),
    response_description="Recommended groups grouped by friend",
    responses={401: UNAUTHORIZED_RESPONSE, 422: VALIDATION_RESPONSE},
)
@inject
async def recommend_groups_by_friends(
    recommendation_service: FromDishka[RecommendationService],
    page: int = Query(default=1, ge=1, description=PAGE_DESCRIPTION),
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of friends to return per page",
    ),
    user_id: str = Depends(verify_access_token),
) -> PaginatedFriendGroupRecommendations:
    return await recommendation_service.recommend_groups_by_friends(
        user_id,
        page,
        limit,
    )
