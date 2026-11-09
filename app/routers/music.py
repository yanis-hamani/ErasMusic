from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query

from app.dependencies import verify_access_token
from app.models.music import (
    Artist,
    Genre,
    PaginatedArtistsResponse,
    PaginatedGenresResponse,
    PaginatedSongsResponse,
    Song,
)
from app.services.music_services import MusicService


router = APIRouter(tags=["Music Data"])


@router.get(
    "/artists",
    response_model=PaginatedArtistsResponse,
    responses={401: {"description": "Unauthorized"}},
)
@inject
async def list_artists(
    music_service: FromDishka[MusicService],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    _user_id: str = Depends(verify_access_token),
) -> PaginatedArtistsResponse:
    return await music_service.list_artists(page, limit)


@router.get(
    "/artists/{artistId}",
    response_model=Artist,
    responses={401: {"description": "Unauthorized"}, 404: {"description": "Not Found"}},
)
@inject
async def get_artist(
    artistId: str,
    music_service: FromDishka[MusicService],
    _user_id: str = Depends(verify_access_token),
) -> Artist:
    return await music_service.get_artist(artistId)


@router.get(
    "/songs",
    response_model=PaginatedSongsResponse,
    responses={401: {"description": "Unauthorized"}},
)
@inject
async def list_songs(
    music_service: FromDishka[MusicService],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    _user_id: str = Depends(verify_access_token),
) -> PaginatedSongsResponse:
    return await music_service.list_songs(page, limit)


@router.get(
    "/songs/{songId}",
    response_model=Song,
    responses={401: {"description": "Unauthorized"}, 404: {"description": "Not Found"}},
)
@inject
async def get_song(
    songId: str,
    music_service: FromDishka[MusicService],
    _user_id: str = Depends(verify_access_token),
) -> Song:
    return await music_service.get_song(songId)


@router.get(
    "/genres",
    response_model=PaginatedGenresResponse,
    responses={401: {"description": "Unauthorized"}},
)
@inject
async def list_genres(
    music_service: FromDishka[MusicService],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    _user_id: str = Depends(verify_access_token),
) -> PaginatedGenresResponse:
    return await music_service.list_genres(page, limit)


@router.get(
    "/genres/{genreId}",
    response_model=Genre,
    responses={401: {"description": "Unauthorized"}, 404: {"description": "Not Found"}},
)
@inject
async def get_genre(
    genreId: str,
    music_service: FromDishka[MusicService],
    _user_id: str = Depends(verify_access_token),
) -> Genre:
    return await music_service.get_genre(genreId)
