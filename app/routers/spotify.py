from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, status

from app.core.openapi import (
    CONFLICT_RESPONSE,
    FORBIDDEN_RESPONSE,
    NOT_FOUND_RESPONSE,
    UNAUTHORIZED_RESPONSE,
    VALIDATION_RESPONSE,
)
from app.dependencies import verify_access_token
from app.models.spotify import (
    SpotifyConnectResponse,
    SpotifyConnectionStatus,
    SpotifySearchResponse,
    SpotifySearchType,
    SpotifySyncResponse,
)
from app.services.spotify_services import SpotifyService


router = APIRouter(prefix="/spotify", tags=["Spotify"])


@router.get(
    "/connect",
    response_model=SpotifyConnectResponse,
    operation_id="connectSpotify",
    summary="Start Spotify authorization",
    description=(
        "Creates a short-lived OAuth state and returns the Spotify authorization "
        "URL that the client must open."
    ),
    response_description="Spotify authorization URL",
    responses={401: UNAUTHORIZED_RESPONSE, 503: {"description": "Spotify is not configured"}},
)
@inject
async def connect_spotify(
    spotify_service: FromDishka[SpotifyService],
    user_id: str = Depends(verify_access_token),
) -> SpotifyConnectResponse:
    return await spotify_service.create_authorization(user_id)


@router.get(
    "/callback",
    response_model=SpotifyConnectionStatus,
    operation_id="completeSpotifyAuthorization",
    summary="Complete Spotify authorization",
    description=(
        "Validates the single-use OAuth state, exchanges the authorization code, "
        "stores encrypted credentials, and attempts the initial top-items sync."
    ),
    response_description="Spotify connection status",
    responses={
        400: {"description": "Invalid, expired, or rejected authorization"},
        409: CONFLICT_RESPONSE,
        502: {"description": "Spotify authorization failed"},
        503: {"description": "Spotify is not configured"},
    },
)
@inject
async def spotify_callback(
    state: str,
    spotify_service: FromDishka[SpotifyService],
    code: str | None = None,
    error: str | None = None,
) -> SpotifyConnectionStatus:
    return await spotify_service.complete_authorization(state, code, error)


@router.get(
    "/status",
    response_model=SpotifyConnectionStatus,
    operation_id="getSpotifyStatus",
    summary="Get Spotify connection status",
    description="Returns connection, synchronization, and reauthorization state.",
    response_description="Spotify connection status",
    responses={401: UNAUTHORIZED_RESPONSE},
)
@inject
async def get_spotify_status(
    spotify_service: FromDishka[SpotifyService],
    user_id: str = Depends(verify_access_token),
) -> SpotifyConnectionStatus:
    return await spotify_service.get_status(user_id)


@router.post(
    "/sync",
    response_model=SpotifySyncResponse,
    operation_id="syncSpotify",
    summary="Synchronize Spotify top items",
    description=(
        "Forces synchronization of the user's top tracks and artists for all "
        "three Spotify time ranges."
    ),
    response_description="Synchronization summary",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        429: {"description": "Spotify rate limit exceeded"},
        502: {"description": "Spotify synchronization failed"},
        503: {"description": "Spotify is not configured"},
    },
)
@inject
async def sync_spotify(
    spotify_service: FromDishka[SpotifyService],
    user_id: str = Depends(verify_access_token),
) -> SpotifySyncResponse:
    return await spotify_service.synchronize(user_id)


@router.delete(
    "/disconnect",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="disconnectSpotify",
    summary="Disconnect Spotify",
    description=(
        "Deletes the stored Spotify credentials and the user's imported track "
        "and artist affinity relationships. Catalog nodes remain available."
    ),
    responses={
        204: {"description": "Spotify disconnected"},
        401: UNAUTHORIZED_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)
@inject
async def disconnect_spotify(
    spotify_service: FromDishka[SpotifyService],
    user_id: str = Depends(verify_access_token),
) -> None:
    await spotify_service.disconnect(user_id)


@router.get(
    "/search",
    response_model=SpotifySearchResponse,
    operation_id="searchSpotify",
    summary="Search the Spotify catalog",
    description=(
        "Searches live Spotify track or artist metadata. Search results are not "
        "persisted in ErasMusic."
    ),
    response_description="Spotify catalog matches",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        429: {"description": "Spotify rate limit exceeded"},
        502: {"description": "Spotify search failed"},
        503: {"description": "Spotify is not configured"},
        422: VALIDATION_RESPONSE,
    },
)
@inject
async def search_spotify(
    spotify_service: FromDishka[SpotifyService],
    q: str = Query(..., min_length=1, pattern=r"\S", description="Search term"),
    type: SpotifySearchType = Query(..., description="Spotify entity type"),
    limit: int = Query(default=5, ge=1, le=10),
    offset: int = Query(default=0, ge=0),
    _user_id: str = Depends(verify_access_token),
) -> SpotifySearchResponse:
    return await spotify_service.search(q, type, limit, offset)
