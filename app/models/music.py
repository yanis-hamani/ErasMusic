from pydantic import BaseModel, Field, HttpUrl

from app.models.common import Pagination


class Artist(BaseModel):
    id: str = Field(..., description="Unique artist identifier", example="artist_1")
    name: str = Field(..., example="Arctic Monkeys")
    profilePictureUrl: HttpUrl | None = Field(
        default=None,
        example="https://example.com/artists/arctic-monkeys.jpg",
    )
    spotifyUrl: HttpUrl | None = Field(
        default=None,
        example="https://open.spotify.com/artist/example",
    )


class Song(BaseModel):
    id: str = Field(..., description="Unique song identifier", example="song_1")
    title: str = Field(..., example="Do I Wanna Know?")
    coverUrl: HttpUrl | None = Field(
        default=None,
        example="https://example.com/covers/song-1.jpg",
    )
    spotifyUrl: HttpUrl | None = Field(
        default=None,
        example="https://open.spotify.com/track/example",
    )
    artists: list[Artist] = Field(
        ...,
        description="Performing artists, or an empty array when none are linked",
    )


class Genre(BaseModel):
    id: str = Field(..., description="Unique genre identifier", example="genre_1")
    name: str = Field(..., example="Indie Rock")


class PaginatedArtistsResponse(BaseModel):
    artists: list[Artist]
    pagination: Pagination


class PaginatedSongsResponse(BaseModel):
    songs: list[Song]
    pagination: Pagination


class PaginatedGenresResponse(BaseModel):
    genres: list[Genre]
    pagination: Pagination
