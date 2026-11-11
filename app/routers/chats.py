from typing import Annotated

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Path, Query, status

from app.core.openapi import (
    CONFLICT_RESPONSE,
    FORBIDDEN_RESPONSE,
    LIMIT_DESCRIPTION,
    NOT_FOUND_RESPONSE,
    PAGE_DESCRIPTION,
    UNAUTHORIZED_RESPONSE,
    VALIDATION_RESPONSE,
)
from app.dependencies import verify_access_token
from app.models.chats import (
    Chat,
    ChatMemberCreate,
    ChatMembership,
    ChatMessage,
    CreateChat,
    PaginatedChatMessagesResponse,
    PaginatedChatsResponse,
    SendMessage,
)
from app.services.chat_services import ChatService


router = APIRouter(prefix="/chats", tags=["Chat"])


@router.get(
    "",
    response_model=PaginatedChatsResponse,
    operation_id="listChats",
    summary="List my conversations",
    description="Conversations are ordered by latest message activity.",
    response_description="User chat conversations",
    responses={401: UNAUTHORIZED_RESPONSE, 422: VALIDATION_RESPONSE},
)
@inject
async def list_chats(
    chat_service: FromDishka[ChatService],
    page: int = Query(default=1, ge=1, description=PAGE_DESCRIPTION),
    limit: int = Query(default=10, ge=1, le=100, description=LIMIT_DESCRIPTION),
    user_id: str = Depends(verify_access_token),
) -> PaginatedChatsResponse:
    return await chat_service.list_chats(user_id, page, limit)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=Chat,
    operation_id="createChat",
    summary="Create a direct or group conversation",
    description=(
        "The authenticated user is included automatically. Direct chats require "
        "an existing friendship and duplicate direct chats are rejected."
    ),
    response_description="Conversation created",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: VALIDATION_RESPONSE,
    },
)
@inject
async def create_chat(
    payload: CreateChat,
    chat_service: FromDishka[ChatService],
    user_id: str = Depends(verify_access_token),
) -> Chat:
    return await chat_service.create_chat(user_id, payload)


@router.get(
    "/{chatId}",
    response_model=Chat,
    operation_id="getChat",
    summary="Get conversation details",
    description="Returns chat metadata when the authenticated user is a participant.",
    response_description="Chat conversation metadata",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)
@inject
async def get_chat(
    chatId: Annotated[
        str,
        Path(description="Unique chat identifier", examples=["chat_101"]),
    ],
    chat_service: FromDishka[ChatService],
    user_id: str = Depends(verify_access_token),
) -> Chat:
    return await chat_service.get_chat(user_id, chatId)


@router.get(
    "/{chatId}/messages",
    response_model=PaginatedChatMessagesResponse,
    operation_id="listChatMessages",
    summary="Retrieve messages",
    description="Messages are ordered newest first, then by ID.",
    response_description="Messages thread",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        422: VALIDATION_RESPONSE,
    },
)
@inject
async def list_chat_messages(
    chatId: Annotated[str, Path(description="Unique chat identifier")],
    chat_service: FromDishka[ChatService],
    page: int = Query(default=1, ge=1, description=PAGE_DESCRIPTION),
    limit: int = Query(default=10, ge=1, le=100, description=LIMIT_DESCRIPTION),
    user_id: str = Depends(verify_access_token),
) -> PaginatedChatMessagesResponse:
    return await chat_service.list_messages(user_id, chatId, page, limit)


@router.post(
    "/{chatId}/messages",
    status_code=status.HTTP_201_CREATED,
    response_model=ChatMessage,
    operation_id="sendChatMessage",
    summary="Send a message",
    description=(
        "Messages in a direct chat update friendship closeness once per UTC day "
        "when both participants have sent a message that day. Group messages do "
        "not affect closeness."
    ),
    response_description="Message posted",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        422: VALIDATION_RESPONSE,
    },
)
@inject
async def send_chat_message(
    chatId: Annotated[str, Path(description="Unique chat identifier")],
    payload: SendMessage,
    chat_service: FromDishka[ChatService],
    user_id: str = Depends(verify_access_token),
) -> ChatMessage:
    return await chat_service.send_message(user_id, chatId, payload)


@router.post(
    "/{chatId}/members",
    status_code=status.HTTP_201_CREATED,
    response_model=ChatMembership,
    operation_id="addChatMember",
    summary="Add a participant",
    description=(
        "Any participant may add users to a standalone group chat. Direct-chat "
        "membership cannot change, and group-owned chats must be managed through "
        "the Groups endpoints."
    ),
    response_description="Participant added",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: VALIDATION_RESPONSE,
    },
)
@inject
async def add_chat_member(
    chatId: Annotated[str, Path(description="Unique chat identifier")],
    payload: ChatMemberCreate,
    chat_service: FromDishka[ChatService],
    user_id: str = Depends(verify_access_token),
) -> ChatMembership:
    return await chat_service.add_member(user_id, chatId, payload)


@router.delete(
    "/{chatId}/members/me",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="leaveChat",
    summary="Leave a conversation",
    description=(
        "Only standalone group chats can be left. The chat and its messages are "
        "deleted when its final participant leaves. Group-owned chats must be "
        "managed through the Groups endpoints."
    ),
    responses={
        204: {"description": "Left conversation"},
        401: UNAUTHORIZED_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        409: {
            **CONFLICT_RESPONSE,
            "description": "Direct or group-owned chat membership cannot be changed",
        },
    },
)
@inject
async def leave_chat(
    chatId: Annotated[str, Path(description="Unique chat identifier")],
    chat_service: FromDishka[ChatService],
    user_id: str = Depends(verify_access_token),
) -> None:
    await chat_service.leave_chat(user_id, chatId)
