from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, status

from app.dependencies import verify_access_token
from app.models.friends import (
    FriendRequest,
    FriendRequestCreate,
    FriendRequestDirection,
    FriendshipStatus,
    PaginatedFriendRequestsResponse,
    PaginatedFriendsResponse,
)
from app.services.friend_services import FriendService


router = APIRouter(tags=["Friends & Social"])


@router.get(
    "/friends",
    response_model=PaginatedFriendsResponse,
    responses={401: {"description": "Unauthorized"}, 404: {"description": "Not Found"}},
)
@inject
async def list_friends(
    friend_service: FromDishka[FriendService],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    user_id: str = Depends(verify_access_token),
) -> PaginatedFriendsResponse:
    return await friend_service.list_friends(user_id, page, limit)


@router.get(
    "/friends/{userId}",
    response_model=FriendshipStatus,
    responses={401: {"description": "Unauthorized"}, 404: {"description": "Not Found"}},
)
@inject
async def get_friendship_status(
    userId: str,
    friend_service: FromDishka[FriendService],
    current_user_id: str = Depends(verify_access_token),
) -> FriendshipStatus:
    return await friend_service.get_friendship_status(current_user_id, userId)


@router.delete(
    "/friends/{userId}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={401: {"description": "Unauthorized"}, 404: {"description": "Not Found"}},
)
@inject
async def remove_friend(
    userId: str,
    friend_service: FromDishka[FriendService],
    current_user_id: str = Depends(verify_access_token),
) -> None:
    await friend_service.remove_friend(current_user_id, userId)


@router.post(
    "/friend-requests",
    status_code=status.HTTP_201_CREATED,
    response_model=FriendRequest,
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Not Found"},
        409: {"description": "Conflict"},
    },
)
@inject
async def create_friend_request(
    payload: FriendRequestCreate,
    friend_service: FromDishka[FriendService],
    user_id: str = Depends(verify_access_token),
) -> FriendRequest:
    return await friend_service.create_friend_request(user_id, payload)


@router.get(
    "/friend-requests",
    response_model=PaginatedFriendRequestsResponse,
    responses={401: {"description": "Unauthorized"}, 404: {"description": "Not Found"}},
)
@inject
async def list_friend_requests(
    friend_service: FromDishka[FriendService],
    direction: FriendRequestDirection = Query(default=FriendRequestDirection.all),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    user_id: str = Depends(verify_access_token),
) -> PaginatedFriendRequestsResponse:
    return await friend_service.list_friend_requests(
        user_id,
        direction,
        page,
        limit,
    )


@router.post(
    "/friend-requests/{requestId}/accept",
    response_model=FriendRequest,
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
        409: {"description": "Conflict"},
    },
)
@inject
async def accept_friend_request(
    requestId: str,
    friend_service: FromDishka[FriendService],
    user_id: str = Depends(verify_access_token),
) -> FriendRequest:
    return await friend_service.accept_friend_request(user_id, requestId)


@router.post(
    "/friend-requests/{requestId}/decline",
    response_model=FriendRequest,
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
        409: {"description": "Conflict"},
    },
)
@inject
async def decline_friend_request(
    requestId: str,
    friend_service: FromDishka[FriendService],
    user_id: str = Depends(verify_access_token),
) -> FriendRequest:
    return await friend_service.decline_friend_request(user_id, requestId)
