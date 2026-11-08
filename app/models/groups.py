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
    artistId: str = Field(..., min_length=1)


class GenreGroupTagInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["genre"]
    genreId: str = Field(..., min_length=1)


GroupTagInput = Annotated[
    ArtistGroupTagInput | GenreGroupTagInput,
    Field(discriminator="type"),
]


class ArtistGroupTag(ArtistGroupTagInput):
    name: str


class GenreGroupTag(GenreGroupTagInput):
    name: str


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
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    tags: list[GroupTagInput] = Field(default_factory=list, max_length=10)

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
    name: str | None = None
    description: str | None = None

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
    tags: list[GroupTagInput] = Field(..., max_length=10)

    @field_validator("tags")
    @classmethod
    def unique_tags(cls, tags: list[GroupTagInput]) -> list[GroupTagInput]:
        return _validate_unique_tags(tags)


class GroupMemberCreate(BaseModel):
    userId: str | None = Field(default=None, min_length=1)


class GroupMember(BaseModel):
    id: str
    username: str
    role: GroupMemberRole
    joinedAt: datetime


class Group(BaseModel):
    id: str
    ownerId: str
    name: str
    description: str
    tags: list[GroupTag]


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
