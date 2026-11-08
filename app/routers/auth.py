from dishka.integrations.fastapi import inject
from app.dependencies import verify_access_token
from app.services.auth_services import AuthService
from dishka import FromDishka
from app.models.auth import AuthTokenResponse, RegisterRequest, AuthLoginRequest, RefreshRequest, RefreshResponse, UserIdentity, LogoutResponse
from fastapi import APIRouter, status, Response, HTTPException, Request, Depends

router = APIRouter(prefix="/auth", tags=["Authentification"])

@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=AuthTokenResponse,
    responses={409: {"description": "Conflict"}, 422: {"description": "Unprocessable Entity"}}
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
 
@router.post("/login", response_model=AuthTokenResponse)
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


@router.post("/refresh", response_model=RefreshResponse)
@inject
async def refresh(
    request: Request,
    payload: RefreshRequest,
    auth_service: FromDishka[AuthService],
) -> RefreshResponse:
    # Try to get token from cookie first, fallback to payload
    token = request.cookies.get("refresh_token") or payload.refreshToken

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token"
        )
    return await auth_service.refresh(token)


@router.post("/logout", response_model=LogoutResponse)
@inject
async def logout(
    request: Request,
    response: Response,
    auth_service: FromDishka[AuthService],
    user_id: str = Depends(verify_access_token),
) -> LogoutResponse:
    refresh_token = request.cookies.get("refresh_token")

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

