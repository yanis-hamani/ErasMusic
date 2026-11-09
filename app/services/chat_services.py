from datetime import datetime, timezone
from math import ceil
from uuid import uuid4

import asyncpg
from fastapi import HTTPException, status
from neo4j import AsyncDriver

from app.models.chats import (
    Chat,
    ChatMemberCreate,
    ChatMembership,
    ChatMessage,
    ChatType,
    CreateChat,
    PaginatedChatMessagesResponse,
    PaginatedChatsResponse,
    SendMessage,
)
from app.models.common import Pagination
from app.repositories.chat_psql_repository import ChatPsqlRepository
from app.repositories.friend_neo_repository import FriendNeoRepository
from app.repositories.group_neo_repository import GroupNeoRepository


class ChatService:
    def __init__(
        self,
        pg_pool: asyncpg.Pool,
        neo4j_driver: AsyncDriver,
        chat_psql_repository: ChatPsqlRepository,
        friend_neo_repository: FriendNeoRepository,
        group_neo_repository: GroupNeoRepository,
    ):
        self.pg_pool = pg_pool
        self.neo4j_driver = neo4j_driver
        self.chat_psql_repository = chat_psql_repository
        self.friend_neo_repository = friend_neo_repository
        self.group_neo_repository = group_neo_repository

    @staticmethod
    def _error(status_code: int, detail: str) -> HTTPException:
        return HTTPException(status_code=status_code, detail=detail)

    @staticmethod
    def _pagination(page: int, limit: int, total: int) -> Pagination:
        return Pagination(
            page=page,
            limit=limit,
            totalItems=total,
            totalPages=ceil(total / limit) if total else 0,
        )

    @staticmethod
    def _require_participant(chat: Chat, user_id: str) -> None:
        if user_id not in chat.participantIds:
            raise ChatService._error(
                status.HTTP_403_FORBIDDEN,
                "You are not a participant of this chat",
            )

    async def _is_group_linked_chat(self, chat_id: str) -> bool:
        async def read(transaction):
            return await self.group_neo_repository.group_chat_exists(
                transaction,
                chat_id,
            )

        async with self.neo4j_driver.session() as session:
            return await session.execute_read(read)

    async def list_chats(
        self,
        user_id: str,
        page: int,
        limit: int,
    ) -> PaginatedChatsResponse:
        async with self.pg_pool.acquire() as connection:
            total = await self.chat_psql_repository.count_user_chats(
                connection,
                user_id,
            )
            chats = await self.chat_psql_repository.list_user_chats(
                connection,
                user_id,
                skip=(page - 1) * limit,
                limit=limit,
            )
        return PaginatedChatsResponse(
            chats=chats,
            pagination=self._pagination(page, limit, total),
        )

    async def create_chat(
        self,
        current_user_id: str,
        payload: CreateChat,
    ) -> Chat:
        if current_user_id in payload.participantIds:
            raise self._error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "The authenticated user is already an implicit participant",
            )

        participant_ids = sorted({current_user_id, *payload.participantIds})
        chat_type = ChatType(payload.type)
        chat_id = f"chat_{uuid4().hex[:12]}"

        try:
            async with self.pg_pool.acquire() as connection:
                async with connection.transaction():
                    if not await self.chat_psql_repository.users_exist(
                        connection,
                        participant_ids,
                    ):
                        raise self._error(
                            status.HTTP_404_NOT_FOUND,
                            "One or more participants were not found",
                        )

                    if chat_type == ChatType.direct:
                        target_user_id = payload.participantIds[0]

                        async def friendship_read(transaction):
                            return await self.friend_neo_repository.friendship_exists(
                                transaction,
                                current_user_id,
                                target_user_id,
                            )

                        async with self.neo4j_driver.session() as session:
                            are_friends = await session.execute_read(friendship_read)
                        if not are_friends:
                            raise self._error(
                                status.HTTP_403_FORBIDDEN,
                                "Direct chats can only be created between friends",
                            )

                        pair_key = ":".join(participant_ids)
                        await self.chat_psql_repository.acquire_direct_pair_lock(
                            connection,
                            pair_key,
                        )
                        existing_chat_id = (
                            await self.chat_psql_repository.find_direct_chat(
                                connection,
                                participant_ids,
                            )
                        )
                        if existing_chat_id is not None:
                            raise self._error(
                                status.HTTP_409_CONFLICT,
                                "A direct chat already exists between these users",
                            )

                    return await self.chat_psql_repository.create_chat(
                        connection,
                        chat_id,
                        chat_type,
                        participant_ids,
                    )
        except asyncpg.ForeignKeyViolationError as error:
            raise self._error(
                status.HTTP_404_NOT_FOUND,
                "One or more participants were not found",
            ) from error
        except asyncpg.UniqueViolationError as error:
            raise self._error(
                status.HTTP_409_CONFLICT,
                "Chat or participant already exists",
            ) from error

    async def get_chat(self, current_user_id: str, chat_id: str) -> Chat:
        async with self.pg_pool.acquire() as connection:
            chat = await self.chat_psql_repository.select_chat(connection, chat_id)
        if chat is None:
            raise self._error(status.HTTP_404_NOT_FOUND, "Chat not found")
        self._require_participant(chat, current_user_id)
        return chat

    async def list_messages(
        self,
        current_user_id: str,
        chat_id: str,
        page: int,
        limit: int,
    ) -> PaginatedChatMessagesResponse:
        async with self.pg_pool.acquire() as connection:
            chat = await self.chat_psql_repository.select_chat(connection, chat_id)
            if chat is None:
                raise self._error(status.HTTP_404_NOT_FOUND, "Chat not found")
            self._require_participant(chat, current_user_id)
            total = await self.chat_psql_repository.count_messages(
                connection,
                chat_id,
            )
            messages = await self.chat_psql_repository.list_messages(
                connection,
                chat_id,
                skip=(page - 1) * limit,
                limit=limit,
            )
        return PaginatedChatMessagesResponse(
            messages=messages,
            pagination=self._pagination(page, limit, total),
        )

    async def send_message(
        self,
        current_user_id: str,
        chat_id: str,
        payload: SendMessage,
    ) -> ChatMessage:
        message_id = f"msg_{uuid4().hex[:16]}"
        created_at = datetime.now(timezone.utc)
        activity_date = created_at.date()

        try:
            async with self.pg_pool.acquire() as connection:
                async with connection.transaction():
                    locked = await self.chat_psql_repository.lock_chat(
                        connection,
                        chat_id,
                    )
                    if locked is None:
                        raise self._error(status.HTTP_404_NOT_FOUND, "Chat not found")
                    self._require_participant(locked.chat, current_user_id)

                    should_increase_closeness = False
                    other_user_id = None
                    if (
                        locked.chat.type == ChatType.direct
                        and locked.last_closeness_activity_date != activity_date
                    ):
                        other_user_id = next(
                            (
                                participant_id
                                for participant_id in locked.chat.participantIds
                                if participant_id != current_user_id
                            ),
                            None,
                        )
                        if other_user_id is not None:
                            should_increase_closeness = await (
                                self.chat_psql_repository.other_participant_messaged_on_date(
                                    connection,
                                    chat_id,
                                    current_user_id,
                                    activity_date,
                                )
                            )

                    message = await self.chat_psql_repository.create_message(
                        connection,
                        message_id,
                        chat_id,
                        current_user_id,
                        payload.message,
                        created_at,
                    )

                    if should_increase_closeness and other_user_id is not None:
                        async def closeness_write(transaction):
                            return await self.friend_neo_repository.increase_closeness(
                                transaction,
                                current_user_id,
                                other_user_id,
                                created_at,
                            )

                        async with self.neo4j_driver.session() as session:
                            await session.execute_write(closeness_write)
                        await self.chat_psql_repository.mark_closeness_activity(
                            connection,
                            chat_id,
                            activity_date,
                        )

                    return message
        except asyncpg.ForeignKeyViolationError as error:
            raise self._error(
                status.HTTP_404_NOT_FOUND,
                "Chat or sender not found",
            ) from error
        except asyncpg.CheckViolationError as error:
            raise self._error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Message must contain between 1 and 4000 non-blank characters",
            ) from error

    async def add_member(
        self,
        current_user_id: str,
        chat_id: str,
        payload: ChatMemberCreate,
    ) -> ChatMembership:
        try:
            async with self.pg_pool.acquire() as connection:
                async with connection.transaction():
                    locked = await self.chat_psql_repository.lock_chat(
                        connection,
                        chat_id,
                    )
                    if locked is None:
                        raise self._error(status.HTTP_404_NOT_FOUND, "Chat not found")
                    self._require_participant(locked.chat, current_user_id)
                    if locked.chat.type == ChatType.direct:
                        raise self._error(
                            status.HTTP_409_CONFLICT,
                            "Direct chat membership cannot be changed",
                        )
                    if await self._is_group_linked_chat(chat_id):
                        raise self._error(
                            status.HTTP_409_CONFLICT,
                            "Group-owned chat membership must be managed through /groups",
                        )
                    if payload.userId in locked.chat.participantIds:
                        raise self._error(
                            status.HTTP_409_CONFLICT,
                            "User is already a chat participant",
                        )
                    if not await self.chat_psql_repository.users_exist(
                        connection,
                        [payload.userId],
                    ):
                        raise self._error(
                            status.HTTP_404_NOT_FOUND,
                            "Target user not found",
                        )
                    await self.chat_psql_repository.add_participant(
                        connection,
                        chat_id,
                        payload.userId,
                    )
                    return ChatMembership(userId=payload.userId, chatId=chat_id)
        except asyncpg.ForeignKeyViolationError as error:
            raise self._error(
                status.HTTP_404_NOT_FOUND,
                "Target user or chat not found",
            ) from error
        except asyncpg.UniqueViolationError as error:
            raise self._error(
                status.HTTP_409_CONFLICT,
                "User is already a chat participant",
            ) from error

    async def leave_chat(self, current_user_id: str, chat_id: str) -> None:
        async with self.pg_pool.acquire() as connection:
            async with connection.transaction():
                locked = await self.chat_psql_repository.lock_chat(
                    connection,
                    chat_id,
                )
                if locked is None:
                    raise self._error(status.HTTP_404_NOT_FOUND, "Chat not found")
                if current_user_id not in locked.chat.participantIds:
                    raise self._error(
                        status.HTTP_404_NOT_FOUND,
                        "Chat participation not found",
                    )
                if locked.chat.type == ChatType.direct:
                    raise self._error(
                        status.HTTP_409_CONFLICT,
                        "Direct chats cannot be left",
                    )
                if await self._is_group_linked_chat(chat_id):
                    raise self._error(
                        status.HTTP_409_CONFLICT,
                        "Group-owned chat membership must be managed through /groups",
                    )
                if not await self.chat_psql_repository.remove_participant(
                    connection,
                    chat_id,
                    current_user_id,
                ):
                    raise self._error(
                        status.HTTP_404_NOT_FOUND,
                        "Chat participation not found",
                    )
                if await self.chat_psql_repository.count_participants(
                    connection,
                    chat_id,
                ) == 0:
                    await self.chat_psql_repository.delete_chat(connection, chat_id)
