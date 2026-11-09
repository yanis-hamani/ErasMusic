from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Query, status

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
    responses={401: {"description": "Unauthorized"}},
)
@inject
async def list_chats(
    chat_service: FromDishka[ChatService],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    user_id: str = Depends(verify_access_token),
) -> PaginatedChatsResponse:
    return await chat_service.list_chats(user_id, page, limit)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=Chat,
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
        409: {"description": "Conflict"},
        422: {"description": "Unprocessable Entity"},
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
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
    },
)
@inject
async def get_chat(
    chatId: str,
    chat_service: FromDishka[ChatService],
    user_id: str = Depends(verify_access_token),
) -> Chat:
    return await chat_service.get_chat(user_id, chatId)


@router.get(
    "/{chatId}/messages",
    response_model=PaginatedChatMessagesResponse,
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
    },
)
@inject
async def list_chat_messages(
    chatId: str,
    chat_service: FromDishka[ChatService],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    user_id: str = Depends(verify_access_token),
) -> PaginatedChatMessagesResponse:
    return await chat_service.list_messages(user_id, chatId, page, limit)


@router.post(
    "/{chatId}/messages",
    status_code=status.HTTP_201_CREATED,
    response_model=ChatMessage,
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
        422: {"description": "Unprocessable Entity"},
    },
)
@inject
async def send_chat_message(
    chatId: str,
    payload: SendMessage,
    chat_service: FromDishka[ChatService],
    user_id: str = Depends(verify_access_token),
) -> ChatMessage:
    return await chat_service.send_message(user_id, chatId, payload)


@router.post(
    "/{chatId}/members",
    status_code=status.HTTP_201_CREATED,
    response_model=ChatMembership,
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
        409: {"description": "Conflict"},
        422: {"description": "Unprocessable Entity"},
    },
)
@inject
async def add_chat_member(
    chatId: str,
    payload: ChatMemberCreate,
    chat_service: FromDishka[ChatService],
    user_id: str = Depends(verify_access_token),
) -> ChatMembership:
    return await chat_service.add_member(user_id, chatId, payload)


@router.delete(
    "/{chatId}/members/me",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Not Found"},
        409: {"description": "Conflict"},
    },
)
@inject
async def leave_chat(
    chatId: str,
    chat_service: FromDishka[ChatService],
    user_id: str = Depends(verify_access_token),
) -> None:
    await chat_service.leave_chat(user_id, chatId)
