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
    id: str
    type: ChatType
    participantIds: list[str]


class CreateDirectChat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["direct"]
    participantIds: list[UserId] = Field(..., min_length=1, max_length=1)


class CreateGroupChat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["group"]
    participantIds: list[UserId] = Field(..., min_length=1)

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
    message: str = Field(..., min_length=1, max_length=4000)

    @field_validator("message")
    @classmethod
    def reject_blank_message(cls, message: str) -> str:
        if not message.strip():
            raise ValueError("Message must not be blank")
        return message


class ChatMessage(BaseModel):
    id: str
    chatId: str
    senderId: str | None
    message: str
    createdAt: datetime


class ChatMemberCreate(BaseModel):
    userId: UserId


class ChatMembership(BaseModel):
    userId: str
    chatId: str


class PaginatedChatsResponse(BaseModel):
    chats: list[Chat]
    pagination: Pagination


class PaginatedChatMessagesResponse(BaseModel):
    messages: list[ChatMessage]
    pagination: Pagination


class LockedChat(BaseModel):
    chat: Chat
    last_closeness_activity_date: date | None = None
