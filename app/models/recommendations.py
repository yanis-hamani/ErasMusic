from enum import Enum

from pydantic import BaseModel, Field

from app.models.common import Pagination
from app.models.groups import Group
from app.models.music import Artist, Genre, Song
from app.models.search import SearchUser


class RecommendationPeriod(str, Enum):
    short_term = "short_term"
    medium_term = "medium_term"
    long_term = "long_term"

    @property
    def score_property(self) -> str:
        return {
            RecommendationPeriod.short_term: "shortTermScore",
            RecommendationPeriod.medium_term: "mediumTermScore",
            RecommendationPeriod.long_term: "longTermScore",
        }[self]


class ArtistUserRecommendations(BaseModel):
    artist: Artist
    users: list[SearchUser] = Field(
        ...,
        max_length=20,
        description="Up to 20 users associated with this artist",
    )


class SongUserRecommendations(BaseModel):
    song: Song
    users: list[SearchUser] = Field(
        ...,
        max_length=20,
        description="Up to 20 users associated with this song",
    )


class FriendUserRecommendations(BaseModel):
    friend: SearchUser
    users: list[SearchUser] = Field(
        ...,
        max_length=20,
        description="Up to 20 recommended users associated with this mutual friend",
    )


class ArtistGroupRecommendations(BaseModel):
    artist: Artist
    groups: list[Group] = Field(
        ...,
        max_length=20,
        description="Up to 20 groups associated with this artist",
    )


class GenreGroupRecommendations(BaseModel):
    genre: Genre
    groups: list[Group] = Field(
        ...,
        max_length=20,
        description="Up to 20 groups associated with this genre",
    )


class FriendGroupRecommendations(BaseModel):
    friend: SearchUser
    groups: list[Group] = Field(
        ...,
        max_length=20,
        description="Up to 20 groups associated with this friend",
    )


class PaginatedArtistUserRecommendations(BaseModel):
    items: list[ArtistUserRecommendations] = Field(
        ...,
        description="Artists and their recommended users",
    )
    pagination: Pagination


class PaginatedSongUserRecommendations(BaseModel):
    items: list[SongUserRecommendations] = Field(
        ...,
        description="Songs and their recommended users",
    )
    pagination: Pagination


class PaginatedFriendUserRecommendations(BaseModel):
    items: list[FriendUserRecommendations] = Field(
        ...,
        description="Recommended users grouped by mutual friend",
    )
    pagination: Pagination


class PaginatedArtistGroupRecommendations(BaseModel):
    items: list[ArtistGroupRecommendations] = Field(
        ...,
        description="Artists and their recommended groups",
    )
    pagination: Pagination


class PaginatedGenreGroupRecommendations(BaseModel):
    items: list[GenreGroupRecommendations] = Field(
        ...,
        description="Genres and their recommended groups",
    )
    pagination: Pagination


class PaginatedFriendGroupRecommendations(BaseModel):
    items: list[FriendGroupRecommendations] = Field(
        ...,
        description="Recommended groups grouped by friend",
    )
    pagination: Pagination
