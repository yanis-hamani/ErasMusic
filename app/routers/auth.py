from typing import Annotated

from dishka.integrations.fastapi import inject
from app.dependencies import verify_access_token
from app.services.auth_services import AuthService
from dishka import FromDishka
from app.models.auth import AuthTokenResponse, RegisterRequest, AuthLoginRequest, RefreshRequest, RefreshResponse, LogoutResponse
from app.core.openapi import (
    CLEARED_REFRESH_COOKIE_HEADER,
    CONFLICT_RESPONSE,
    NOT_FOUND_RESPONSE,
    REFRESH_COOKIE_DESCRIPTION,
    REFRESH_COOKIE_HEADER,
    UNAUTHORIZED_RESPONSE,
    VALIDATION_RESPONSE,
)
from fastapi import APIRouter, Body, Cookie, status, Response, HTTPException, Depends

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=AuthTokenResponse,
    operation_id="registerUser",
    summary="Create an account",
    description=(
        "Creates a user in PostgreSQL and a corresponding User node in Neo4j. "
        "The password is hashed before storage. A refresh token is returned in "
        "an HTTP-only cookie."
    ),
    response_description="Account created successfully",
    responses={
        201: {"headers": {"Set-Cookie": REFRESH_COOKIE_HEADER}},
        409: CONFLICT_RESPONSE,
        422: VALIDATION_RESPONSE,
    },
)
@inject
async def register(
    payload : RegisterRequest,
    response: Response,
    auth_service: FromDishka[AuthService],
) -> AuthTokenResponse:
    auth_response, refresh_token = await auth_service.register(payload)

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True, # TODO: Ensure you are using HTTPS, am I ?:
        samesite="lax"
    )
    return auth_response
 
@router.post(
    "/login",
    response_model=AuthTokenResponse,
    operation_id="loginUser",
    summary="Authenticate a user",
    description=(
        "Validates the user's credentials, returns an access token, and stores "
        "a refresh token in an HTTP-only cookie."
    ),
    response_description="Authenticated successfully",
    responses={
        200: {"headers": {"Set-Cookie": REFRESH_COOKIE_HEADER}},
        401: UNAUTHORIZED_RESPONSE,
        422: VALIDATION_RESPONSE,
    },
)
@inject
async def login(
    payload: AuthLoginRequest,
    response: Response,
    auth_service: FromDishka[AuthService],
) ->AuthTokenResponse:
    auth_response, refresh_token = await auth_service.login(payload)

    # Set HTTP-only cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax"
    )

    return auth_response


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    operation_id="refreshAccessToken",
    summary="Refresh access token/session",
    description=(
        "Generates a new access token from a valid refresh token. The "
        "refresh_token cookie takes precedence over refreshToken in the JSON "
        "body. Send an empty object when authenticating only with the cookie."
    ),
    response_description="Token refreshed",
    responses={401: UNAUTHORIZED_RESPONSE, 422: VALIDATION_RESPONSE},
)
@inject
async def refresh(
    payload: Annotated[
        RefreshRequest,
        Body(
            description=(
                "Supply refreshToken here, or send an empty object when using "
                "the cookie."
            )
        ),
    ],
    auth_service: FromDishka[AuthService],
    refresh_token: Annotated[
        str | None,
        Cookie(description=REFRESH_COOKIE_DESCRIPTION),
    ] = None,
) -> RefreshResponse:
    token = refresh_token or payload.refreshToken

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token"
        )
    return await auth_service.refresh(token)


@router.post(
    "/logout",
    response_model=LogoutResponse,
    operation_id="logoutUser",
    summary="End the current session",
    description=(
        "Validates the access token, deletes the current refresh token from "
        "storage when its cookie is present, and clears the refresh-token "
        "cookie. The access JWT remains valid until it expires."
    ),
    response_description="Logged out successfully",
    responses={
        200: {"headers": {"Set-Cookie": CLEARED_REFRESH_COOKIE_HEADER}},
        401: UNAUTHORIZED_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)
@inject
async def logout(
    response: Response,
    auth_service: FromDishka[AuthService],
    user_id: str = Depends(verify_access_token),
    refresh_token: Annotated[
        str | None,
        Cookie(description=REFRESH_COOKIE_DESCRIPTION),
    ] = None,
) -> LogoutResponse:
    if refresh_token:
        await auth_service.delete_refresh_token(refresh_token, user_id)

    # Delete the cookie regardless
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=True,
        samesite="lax"
    )

    return LogoutResponse(message="Session terminated successfully")
