from enum import Enum

from pydantic import BaseModel

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
    users: list[SearchUser]


class SongUserRecommendations(BaseModel):
    song: Song
    users: list[SearchUser]


class FriendUserRecommendations(BaseModel):
    friend: SearchUser
    users: list[SearchUser]


class ArtistGroupRecommendations(BaseModel):
    artist: Artist
    groups: list[Group]


class GenreGroupRecommendations(BaseModel):
    genre: Genre
    groups: list[Group]


class FriendGroupRecommendations(BaseModel):
    friend: SearchUser
    groups: list[Group]


class PaginatedArtistUserRecommendations(BaseModel):
    items: list[ArtistUserRecommendations]
    pagination: Pagination


class PaginatedSongUserRecommendations(BaseModel):
    items: list[SongUserRecommendations]
    pagination: Pagination


class PaginatedFriendUserRecommendations(BaseModel):
    items: list[FriendUserRecommendations]
    pagination: Pagination


class PaginatedArtistGroupRecommendations(BaseModel):
    items: list[ArtistGroupRecommendations]
    pagination: Pagination


class PaginatedGenreGroupRecommendations(BaseModel):
    items: list[GenreGroupRecommendations]
    pagination: Pagination


class PaginatedFriendGroupRecommendations(BaseModel):
    items: list[FriendGroupRecommendations]
    pagination: Pagination
