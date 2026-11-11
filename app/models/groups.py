from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.common import Pagination


class GroupMemberRole(str, Enum):
    owner = "owner"
    member = "member"


class ArtistGroupTagInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["artist"]
    artistId: str = Field(..., min_length=1, example="artist_1")


class GenreGroupTagInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["genre"]
    genreId: str = Field(..., min_length=1, example="genre_1")


GroupTagInput = Annotated[
    ArtistGroupTagInput | GenreGroupTagInput,
    Field(discriminator="type"),
]


class ArtistGroupTag(ArtistGroupTagInput):
    model_config = ConfigDict(title="Artist tag")

    artistId: str = Field(
        ...,
        min_length=1,
        description="ID of the artist in the music catalog",
        example="artist_1",
    )
    name: str = Field(..., description="Artist name", example="Arctic Monkeys")


class GenreGroupTag(GenreGroupTagInput):
    model_config = ConfigDict(title="Genre tag")

    genreId: str = Field(
        ...,
        min_length=1,
        description="ID of the genre in the music catalog",
        example="genre_1",
    )
    name: str = Field(..., description="Genre name", example="indie")


GroupTag = Annotated[ArtistGroupTag | GenreGroupTag, Field(discriminator="type")]


def _validate_unique_tags(tags: list[GroupTagInput]) -> list[GroupTagInput]:
    keys = {
        (tag.type, tag.artistId if tag.type == "artist" else tag.genreId)
        for tag in tags
    }
    if len(keys) != len(tags):
        raise ValueError("Group tags must be unique")
    return tags


class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1, example="Indie Music Lovers")
    description: str = Field(
        ...,
        min_length=1,
        example="Discover and discuss indie music",
    )
    tags: list[GroupTagInput] = Field(
        default_factory=list,
        max_length=10,
        json_schema_extra={"uniqueItems": True},
    )

    @field_validator("name", "description")
    @classmethod
    def strip_non_empty_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value must not be blank")
        return value

    @field_validator("tags")
    @classmethod
    def unique_tags(cls, tags: list[GroupTagInput]) -> list[GroupTagInput]:
        return _validate_unique_tags(tags)


class GroupUpdate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"minProperties": 1})

    name: str | None = Field(default=None, min_length=1)
    description: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_update(self) -> "GroupUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one group field must be provided")
        for field in self.model_fields_set:
            value = getattr(self, field)
            if value is None or not value.strip():
                raise ValueError(f"{field} must not be blank or null")
            setattr(self, field, value.strip())
        return self


class GroupTagsReplace(BaseModel):
    tags: list[GroupTagInput] = Field(
        ...,
        max_length=10,
        json_schema_extra={"uniqueItems": True},
    )

    @field_validator("tags")
    @classmethod
    def unique_tags(cls, tags: list[GroupTagInput]) -> list[GroupTagInput]:
        return _validate_unique_tags(tags)


class GroupMemberCreate(BaseModel):
    userId: str | None = Field(
        default=None,
        min_length=1,
        description="Optional target user; defaults to the authenticated user",
        example="usr_a1b2c3d4e5f6",
    )


class GroupMember(BaseModel):
    id: str = Field(..., example="usr_a1b2c3d4e5f6")
    username: str = Field(..., example="alex")
    role: GroupMemberRole = Field(..., description="Membership role")
    joinedAt: datetime = Field(..., description="Time the user joined the group")


class Group(BaseModel):
    id: str = Field(..., example="grp_123")
    ownerId: str = Field(..., example="usr_a1b2c3d4e5f6")
    name: str = Field(..., example="Indie Music Lovers")
    description: str = Field(..., example="Discover and discuss indie music")
    tags: list[GroupTag] = Field(
        ...,
        max_length=10,
        json_schema_extra={"uniqueItems": True},
    )


class GroupRecord(BaseModel):
    id: str
    psql_chat_id: str
    owner_id: str
    name: str
    description: str


class PaginatedGroupsResponse(BaseModel):
    groups: list[Group]
    pagination: Pagination


class PaginatedGroupMembersResponse(BaseModel):
    members: list[GroupMember]
    pagination: Pagination
