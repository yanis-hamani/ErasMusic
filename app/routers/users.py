from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Response, status

from app.dependencies import verify_access_token
from app.models.users import PrivateUserProfile, PublicUserProfile, UserProfileUpdate
from app.services.user_services import UserService


router = APIRouter(prefix="/users", tags=["User Profiles"])


@router.get(
    "/me",
    response_model=PrivateUserProfile,
    responses={401: {"description": "Unauthorized"}, 404: {"description": "Not Found"}},
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
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Not Found"},
        422: {"description": "Unprocessable Entity"},
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
    responses={401: {"description": "Unauthorized"}, 404: {"description": "Not Found"}},
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
    responses={401: {"description": "Unauthorized"}, 404: {"description": "Not Found"}},
)
@inject
async def get_public_user_profile(
    userId: str,
    user_service: FromDishka[UserService],
    _authenticated_user_id: str = Depends(verify_access_token),
) -> PublicUserProfile:
    return await user_service.get_public_profile(userId)
