from typing import Annotated

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Path, Query, status

from app.core.openapi import (
    CONFLICT_RESPONSE,
    FORBIDDEN_RESPONSE,
    LIMIT_DESCRIPTION,
    NOT_FOUND_RESPONSE,
    PAGE_DESCRIPTION,
    UNAUTHORIZED_RESPONSE,
    VALIDATION_RESPONSE,
)
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
    operation_id="listFriends",
    summary="List my friends",
    description=(
        "Retrieves friends from Neo4j. A friendship is stored as one "
        "FRIENDS_WITH relationship and queried without direction."
    ),
    response_description="Paginated friends list",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        422: VALIDATION_RESPONSE,
    },
)
@inject
async def list_friends(
    friend_service: FromDishka[FriendService],
    page: int = Query(default=1, ge=1, description=PAGE_DESCRIPTION),
    limit: int = Query(default=10, ge=1, le=100, description=LIMIT_DESCRIPTION),
    user_id: str = Depends(verify_access_token),
) -> PaginatedFriendsResponse:
    return await friend_service.list_friends(user_id, page, limit)


@router.get(
    "/friends/{userId}",
    response_model=FriendshipStatus,
    operation_id="getFriendshipStatus",
    summary="Get friendship status with a user",
    description=(
        "Returns the friendship status between the authenticated user and the "
        "specified user. The status indicates whether the users are friends, "
        "have a pending friend request, or have no existing relationship."
    ),
    response_description="Friendship status retrieved successfully",
    responses={401: UNAUTHORIZED_RESPONSE, 404: NOT_FOUND_RESPONSE},
)
@inject
async def get_friendship_status(
    userId: Annotated[
        str,
        Path(
            description="ID of the user whose friendship status you want to check",
            examples=["usr_456"],
        ),
    ],
    friend_service: FromDishka[FriendService],
    current_user_id: str = Depends(verify_access_token),
) -> FriendshipStatus:
    return await friend_service.get_friendship_status(current_user_id, userId)


@router.delete(
    "/friends/{userId}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="removeFriend",
    summary="Remove a friend",
    description="Deletes the friendship relationship from the Neo4j graph.",
    responses={
        204: {"description": "Friendship removed"},
        401: UNAUTHORIZED_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)
@inject
async def remove_friend(
    userId: Annotated[str, Path(description="Unique user identifier")],
    friend_service: FromDishka[FriendService],
    current_user_id: str = Depends(verify_access_token),
) -> None:
    await friend_service.remove_friend(current_user_id, userId)


@router.post(
    "/friend-requests",
    status_code=status.HTTP_201_CREATED,
    response_model=FriendRequest,
    operation_id="createFriendRequest",
    summary="Send a friend request",
    description=(
        "Creates a pending directed request. Requests to oneself, duplicate or "
        "crossed requests, and requests between existing friends return a conflict."
    ),
    response_description="Friend request created",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: VALIDATION_RESPONSE,
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
    operation_id="listFriendRequests",
    summary="List incoming and outgoing requests",
    description="Returns pending requests ordered from newest to oldest.",
    response_description="Paginated friend requests list",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        422: VALIDATION_RESPONSE,
    },
)
@inject
async def list_friend_requests(
    friend_service: FromDishka[FriendService],
    direction: FriendRequestDirection = Query(
        default=FriendRequestDirection.all,
        description="Filter incoming, outgoing, or all pending requests",
    ),
    page: int = Query(default=1, ge=1, description=PAGE_DESCRIPTION),
    limit: int = Query(default=10, ge=1, le=100, description=LIMIT_DESCRIPTION),
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
    operation_id="acceptFriendRequest",
    summary="Accept a request",
    description=(
        "Marks the request as accepted and creates the friendship relationship "
        "in Neo4j. The processed request relationship is then deleted."
    ),
    response_description="Request accepted and friendship established",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
    },
)
@inject
async def accept_friend_request(
    requestId: Annotated[str, Path(description="Unique friend-request identifier")],
    friend_service: FromDishka[FriendService],
    user_id: str = Depends(verify_access_token),
) -> FriendRequest:
    return await friend_service.accept_friend_request(user_id, requestId)


@router.post(
    "/friend-requests/{requestId}/decline",
    response_model=FriendRequest,
    operation_id="declineFriendRequest",
    summary="Decline a request",
    description="Deletes the pending request after returning it with declined status.",
    response_description="Request declined",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
    },
)
@inject
async def decline_friend_request(
    requestId: Annotated[str, Path(description="Unique friend-request identifier")],
    friend_service: FromDishka[FriendService],
    user_id: str = Depends(verify_access_token),
) -> FriendRequest:
    return await friend_service.decline_friend_request(user_id, requestId)
