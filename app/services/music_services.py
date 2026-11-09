from math import ceil

from fastapi import HTTPException, status
from neo4j import AsyncDriver

from app.models.common import Pagination
from app.models.music import (
    Artist,
    Genre,
    PaginatedArtistsResponse,
    PaginatedGenresResponse,
    PaginatedSongsResponse,
    Song,
)
from app.repositories.music_neo_repository import MusicNeoRepository


class MusicService:
    def __init__(
        self,
        neo4j_driver: AsyncDriver,
        music_neo_repository: MusicNeoRepository,
    ):
        self.neo4j_driver = neo4j_driver
        self.music_neo_repository = music_neo_repository

    @staticmethod
    def _pagination(page: int, limit: int, total: int) -> Pagination:
        return Pagination(
            page=page,
            limit=limit,
            totalItems=total,
            totalPages=ceil(total / limit) if total else 0,
        )

    @staticmethod
    def _not_found(entity: str) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{entity} not found",
        )

    async def list_artists(self, page: int, limit: int) -> PaginatedArtistsResponse:
        async def read(transaction):
            total = await self.music_neo_repository.count_artists(transaction)
            artists = await self.music_neo_repository.list_artists(
                transaction,
                skip=(page - 1) * limit,
                limit=limit,
            )
            return PaginatedArtistsResponse(
                artists=artists,
                pagination=self._pagination(page, limit, total),
            )

        async with self.neo4j_driver.session() as session:
            return await session.execute_read(read)

    async def get_artist(self, artist_id: str) -> Artist:
        async def read(transaction):
            artist = await self.music_neo_repository.select_artist(
                transaction,
                artist_id,
            )
            if artist is None:
                raise self._not_found("Artist")
            return artist

        async with self.neo4j_driver.session() as session:
            return await session.execute_read(read)

    async def list_songs(self, page: int, limit: int) -> PaginatedSongsResponse:
        async def read(transaction):
            total = await self.music_neo_repository.count_songs(transaction)
            songs = await self.music_neo_repository.list_songs(
                transaction,
                skip=(page - 1) * limit,
                limit=limit,
            )
            return PaginatedSongsResponse(
                songs=songs,
                pagination=self._pagination(page, limit, total),
            )

        async with self.neo4j_driver.session() as session:
            return await session.execute_read(read)

    async def get_song(self, song_id: str) -> Song:
        async def read(transaction):
            song = await self.music_neo_repository.select_song(transaction, song_id)
            if song is None:
                raise self._not_found("Song")
            return song

        async with self.neo4j_driver.session() as session:
            return await session.execute_read(read)

    async def list_genres(self, page: int, limit: int) -> PaginatedGenresResponse:
        async def read(transaction):
            total = await self.music_neo_repository.count_genres(transaction)
            genres = await self.music_neo_repository.list_genres(
                transaction,
                skip=(page - 1) * limit,
                limit=limit,
            )
            return PaginatedGenresResponse(
                genres=genres,
                pagination=self._pagination(page, limit, total),
            )

        async with self.neo4j_driver.session() as session:
            return await session.execute_read(read)

    async def get_genre(self, genre_id: str) -> Genre:
        async def read(transaction):
            genre = await self.music_neo_repository.select_genre(transaction, genre_id)
            if genre is None:
                raise self._not_found("Genre")
            return genre

        async with self.neo4j_driver.session() as session:
            return await session.execute_read(read)
