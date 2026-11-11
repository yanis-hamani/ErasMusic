from typing import Annotated

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Path, Response, status

from app.core.openapi import (
    CLEARED_REFRESH_COOKIE_HEADER,
    NOT_FOUND_RESPONSE,
    UNAUTHORIZED_RESPONSE,
    VALIDATION_RESPONSE,
)
from app.dependencies import verify_access_token
from app.models.users import PrivateUserProfile, PublicUserProfile, UserProfileUpdate
from app.services.user_services import UserService


router = APIRouter(prefix="/users", tags=["User Profiles"])


@router.get(
    "/me",
    response_model=PrivateUserProfile,
    operation_id="getCurrentUserProfile",
    summary="Get my profile",
    description="Retrieves the authenticated user's private profile.",
    response_description="Profile object",
    responses={401: UNAUTHORIZED_RESPONSE, 404: NOT_FOUND_RESPONSE},
)
@inject
async def get_current_user_profile(
    user_service: FromDishka[UserService],
    user_id: str = Depends(verify_access_token),
) -> PrivateUserProfile:
    return await user_service.get_private_profile(user_id)


@router.patch(
    "/me",
    response_model=PrivateUserProfile,
    operation_id="updateCurrentUserProfile",
    summary="Update my profile",
    description="Updates the current user's profile metadata in PostgreSQL.",
    response_description="Profile updated",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        422: VALIDATION_RESPONSE,
    },
)
@inject
async def update_current_user_profile(
    payload: UserProfileUpdate,
    user_service: FromDishka[UserService],
    user_id: str = Depends(verify_access_token),
) -> PrivateUserProfile:
    return await user_service.update_profile(user_id, payload)


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteCurrentUser",
    summary="Delete my account",
    description="Permanently deletes the user account, profile, and associated records.",
    responses={
        204: {
            "description": "Account deleted successfully",
            "headers": {"Set-Cookie": CLEARED_REFRESH_COOKIE_HEADER},
        },
        401: UNAUTHORIZED_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)
@inject
async def delete_current_user(
    response: Response,
    user_service: FromDishka[UserService],
    user_id: str = Depends(verify_access_token),
) -> None:
    await user_service.delete_user(user_id)
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=True,
        samesite="lax",
    )


@router.get(
    "/{userId}",
    response_model=PublicUserProfile,
    operation_id="getPublicUserProfile",
    summary="View a public profile",
    description="Retrieves the public profile for the specified user ID.",
    response_description="Public user profile",
    responses={401: UNAUTHORIZED_RESPONSE, 404: NOT_FOUND_RESPONSE},
)
@inject
async def get_public_user_profile(
    userId: Annotated[
        str,
        Path(description="Unique user identifier", examples=["usr_123"]),
    ],
    user_service: FromDishka[UserService],
    _authenticated_user_id: str = Depends(verify_access_token),
) -> PublicUserProfile:
    return await user_service.get_public_profile(userId)
