from datetime import date, datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.common import Pagination


UserId = Annotated[str, Field(min_length=1)]


class ChatType(str, Enum):
    direct = "direct"
    group = "group"


class Chat(BaseModel):
    id: str = Field(..., example="chat_101")
    type: ChatType = Field(..., example="direct")
    participantIds: list[UserId] = Field(
        ...,
        min_length=1,
        example=["usr_123", "usr_456"],
        json_schema_extra={"uniqueItems": True},
    )


class CreateDirectChat(BaseModel):
    """The authenticated user is implicit; provide exactly one other user."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["direct"]
    participantIds: list[UserId] = Field(
        ...,
        min_length=1,
        max_length=1,
        example=["usr_456"],
        json_schema_extra={"uniqueItems": True},
    )


class CreateGroupChat(BaseModel):
    """The authenticated user is implicit; provide the other initial participants."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["group"]
    participantIds: list[UserId] = Field(
        ...,
        min_length=1,
        example=["usr_456", "usr_789"],
        json_schema_extra={"uniqueItems": True},
    )

    @field_validator("participantIds")
    @classmethod
    def unique_participants(cls, participant_ids: list[str]) -> list[str]:
        if len(set(participant_ids)) != len(participant_ids):
            raise ValueError("Participant IDs must be unique")
        return participant_ids


CreateChat = Annotated[
    CreateDirectChat | CreateGroupChat,
    Field(discriminator="type"),
]


class SendMessage(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        example="Have you listened to their new album?",
    )

    @field_validator("message")
    @classmethod
    def reject_blank_message(cls, message: str) -> str:
        if not message.strip():
            raise ValueError("Message must not be blank")
        return message


class ChatMessage(BaseModel):
    id: str = Field(..., example="msg_999")
    chatId: str = Field(..., example="chat_101")
    senderId: str | None = Field(
        ...,
        description="Null when the sender's account has been deleted",
        example="usr_123",
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        example="Have you listened to their new album?",
    )
    createdAt: datetime = Field(..., description="Message creation time")


class ChatMemberCreate(BaseModel):
    userId: UserId = Field(..., example="usr_789")


class ChatMembership(BaseModel):
    userId: str = Field(..., example="usr_789")
    chatId: str = Field(..., example="chat_123")


class PaginatedChatsResponse(BaseModel):
    chats: list[Chat]
    pagination: Pagination


class PaginatedChatMessagesResponse(BaseModel):
    messages: list[ChatMessage]
    pagination: Pagination


class LockedChat(BaseModel):
    chat: Chat
    last_closeness_activity_date: date | None = None
