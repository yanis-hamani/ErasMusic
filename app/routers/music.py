from typing import Annotated

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Path, Query

from app.core.openapi import (
    LIMIT_DESCRIPTION,
    NOT_FOUND_RESPONSE,
    PAGE_DESCRIPTION,
    UNAUTHORIZED_RESPONSE,
    VALIDATION_RESPONSE,
)
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
    operation_id="listArtists",
    summary="Browse or list artists",
    description="Artists are ordered alphabetically by name and then by ID.",
    response_description="Artist details",
    responses={401: UNAUTHORIZED_RESPONSE, 422: VALIDATION_RESPONSE},
)
@inject
async def list_artists(
    music_service: FromDishka[MusicService],
    page: int = Query(default=1, ge=1, description=PAGE_DESCRIPTION),
    limit: int = Query(default=10, ge=1, le=100, description=LIMIT_DESCRIPTION),
    _user_id: str = Depends(verify_access_token),
) -> PaginatedArtistsResponse:
    return await music_service.list_artists(page, limit)


@router.get(
    "/artists/{artistId}",
    response_model=Artist,
    operation_id="getArtist",
    summary="Get artist details",
    description="Returns one artist from the Neo4j music catalog.",
    response_description="Artist details",
    responses={401: UNAUTHORIZED_RESPONSE, 404: NOT_FOUND_RESPONSE},
)
@inject
async def get_artist(
    artistId: Annotated[
        str,
        Path(description="Unique artist identifier", examples=["artist_1"]),
    ],
    music_service: FromDishka[MusicService],
    _user_id: str = Depends(verify_access_token),
) -> Artist:
    return await music_service.get_artist(artistId)


@router.get(
    "/songs",
    response_model=PaginatedSongsResponse,
    operation_id="listSongs",
    summary="Browse or list songs",
    description=(
        "Songs are ordered alphabetically by title and then by ID. Songs without "
        "a performing artist remain visible with an empty artists array."
    ),
    response_description="Song catalog list",
    responses={401: UNAUTHORIZED_RESPONSE, 422: VALIDATION_RESPONSE},
)
@inject
async def list_songs(
    music_service: FromDishka[MusicService],
    page: int = Query(default=1, ge=1, description=PAGE_DESCRIPTION),
    limit: int = Query(default=10, ge=1, le=100, description=LIMIT_DESCRIPTION),
    _user_id: str = Depends(verify_access_token),
) -> PaginatedSongsResponse:
    return await music_service.list_songs(page, limit)


@router.get(
    "/songs/{songId}",
    response_model=Song,
    operation_id="getSong",
    summary="Get song details",
    description="Returns one song and its performing artists.",
    response_description="Song details",
    responses={401: UNAUTHORIZED_RESPONSE, 404: NOT_FOUND_RESPONSE},
)
@inject
async def get_song(
    songId: Annotated[
        str,
        Path(description="Unique song identifier", examples=["song_1"]),
    ],
    music_service: FromDishka[MusicService],
    _user_id: str = Depends(verify_access_token),
) -> Song:
    return await music_service.get_song(songId)


@router.get(
    "/genres",
    response_model=PaginatedGenresResponse,
    operation_id="listGenres",
    summary="Browse genres",
    description="Genres are ordered alphabetically by name and then by ID.",
    response_description="List of genres",
    responses={401: UNAUTHORIZED_RESPONSE, 422: VALIDATION_RESPONSE},
)
@inject
async def list_genres(
    music_service: FromDishka[MusicService],
    page: int = Query(default=1, ge=1, description=PAGE_DESCRIPTION),
    limit: int = Query(default=10, ge=1, le=100, description=LIMIT_DESCRIPTION),
    _user_id: str = Depends(verify_access_token),
) -> PaginatedGenresResponse:
    return await music_service.list_genres(page, limit)


@router.get(
    "/genres/{genreId}",
    response_model=Genre,
    operation_id="getGenre",
    summary="Get genre details",
    description="Returns one genre from the Neo4j music catalog.",
    response_description="Genre details",
    responses={401: UNAUTHORIZED_RESPONSE, 404: NOT_FOUND_RESPONSE},
)
@inject
async def get_genre(
    genreId: Annotated[str, Path(description="Unique genre identifier")],
    music_service: FromDishka[MusicService],
    _user_id: str = Depends(verify_access_token),
) -> Genre:
    return await music_service.get_genre(genreId)
