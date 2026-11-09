from pydantic import BaseModel, Field, HttpUrl

from app.models.common import Pagination


class Artist(BaseModel):
    id: str = Field(..., description="Unique artist identifier")
    name: str
    profilePictureUrl: HttpUrl | None = None
    spotifyUrl: HttpUrl | None = None


class Song(BaseModel):
    id: str = Field(..., description="Unique song identifier")
    title: str
    coverUrl: HttpUrl | None = None
    spotifyUrl: HttpUrl | None = None
    artists: list[Artist]


class Genre(BaseModel):
    id: str = Field(..., description="Unique genre identifier")
    name: str


class PaginatedArtistsResponse(BaseModel):
    artists: list[Artist]
    pagination: Pagination


class PaginatedSongsResponse(BaseModel):
    songs: list[Song]
    pagination: Pagination


class PaginatedGenresResponse(BaseModel):
    genres: list[Genre]
    pagination: Pagination
