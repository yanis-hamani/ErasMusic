from datetime import date, datetime

from app.models.chats import Chat, ChatMessage, ChatType, LockedChat


class ChatPsqlRepository:
    @staticmethod
    async def create_group_chat(psql_conn, chat_id: str, owner_id: str) -> None:
        await psql_conn.execute(
            "INSERT INTO chats (id, type) VALUES ($1, 'group')",
            chat_id,
        )
        await psql_conn.execute(
            "INSERT INTO chat_participants (chat_id, user_id) VALUES ($1, $2)",
            chat_id,
            owner_id,
        )

    @staticmethod
    async def create_chat(
        psql_conn,
        chat_id: str,
        chat_type: ChatType,
        participant_ids: list[str],
    ) -> Chat:
        await psql_conn.execute(
            "INSERT INTO chats (id, type) VALUES ($1, $2)",
            chat_id,
            chat_type.value,
        )
        for participant_id in participant_ids:
            await psql_conn.execute(
                "INSERT INTO chat_participants (chat_id, user_id) VALUES ($1, $2)",
                chat_id,
                participant_id,
            )
        return Chat(
            id=chat_id,
            type=chat_type,
            participantIds=sorted(participant_ids),
        )

    @staticmethod
    async def acquire_direct_pair_lock(psql_conn, pair_key: str) -> None:
        await psql_conn.fetchval(
            "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))",
            pair_key,
        )

    @staticmethod
    async def find_direct_chat(
        psql_conn,
        participant_ids: list[str],
    ) -> str | None:
        return await psql_conn.fetchval(
            """
            SELECT chat.id
            FROM chats AS chat
            JOIN chat_participants AS participant
              ON participant.chat_id = chat.id
            WHERE chat.type = 'direct'
            GROUP BY chat.id
            HAVING count(*) = 2
               AND bool_and(participant.user_id = ANY($1::varchar[]))
            LIMIT 1
            """,
            participant_ids,
        )

    @staticmethod
    async def users_exist(psql_conn, user_ids: list[str]) -> bool:
        existing = await psql_conn.fetchval(
            "SELECT count(*) FROM users WHERE id = ANY($1::varchar[])",
            user_ids,
        )
        return int(existing) == len(set(user_ids))

    @staticmethod
    async def count_user_chats(psql_conn, user_id: str) -> int:
        return int(
            await psql_conn.fetchval(
                "SELECT count(*) FROM chat_participants WHERE user_id = $1",
                user_id,
            )
        )

    @staticmethod
    async def list_user_chats(
        psql_conn,
        user_id: str,
        skip: int,
        limit: int,
    ) -> list[Chat]:
        records = await psql_conn.fetch(
            """
            SELECT chat.id,
                   chat.type,
                   ARRAY(
                       SELECT participant.user_id
                       FROM chat_participants AS participant
                       WHERE participant.chat_id = chat.id
                       ORDER BY participant.user_id
                   ) AS participant_ids
            FROM chats AS chat
            JOIN chat_participants AS current_participant
              ON current_participant.chat_id = chat.id
             AND current_participant.user_id = $1
            ORDER BY (
                         SELECT max(message.created_at)
                         FROM chat_messages AS message
                         WHERE message.chat_id = chat.id
                     ) DESC NULLS LAST,
                     chat.created_at DESC,
                     chat.id
            OFFSET $2
            LIMIT $3
            """,
            user_id,
            skip,
            limit,
        )
        return [ChatPsqlRepository._chat(record) for record in records]

    @staticmethod
    async def select_chat(psql_conn, chat_id: str) -> Chat | None:
        record = await psql_conn.fetchrow(
            """
            SELECT chat.id,
                   chat.type,
                   ARRAY(
                       SELECT participant.user_id
                       FROM chat_participants AS participant
                       WHERE participant.chat_id = chat.id
                       ORDER BY participant.user_id
                   ) AS participant_ids
            FROM chats AS chat
            WHERE chat.id = $1
            """,
            chat_id,
        )
        return ChatPsqlRepository._chat(record)

    @staticmethod
    async def lock_chat(psql_conn, chat_id: str) -> LockedChat | None:
        record = await psql_conn.fetchrow(
            """
            SELECT id, type, last_closeness_activity_date
            FROM chats
            WHERE id = $1
            FOR UPDATE
            """,
            chat_id,
        )
        if not record:
            return None
        participant_records = await psql_conn.fetch(
            """
            SELECT user_id
            FROM chat_participants
            WHERE chat_id = $1
            ORDER BY user_id
            """,
            chat_id,
        )
        return LockedChat(
            chat=Chat(
                id=record["id"],
                type=ChatType(record["type"]),
                participantIds=[row["user_id"] for row in participant_records],
            ),
            last_closeness_activity_date=record[
                "last_closeness_activity_date"
            ],
        )

    @staticmethod
    async def delete_chat(psql_conn, chat_id: str) -> bool:
        deleted_id = await psql_conn.fetchval(
            "DELETE FROM chats WHERE id = $1 RETURNING id",
            chat_id,
        )
        return deleted_id is not None

    @staticmethod
    async def add_participant(psql_conn, chat_id: str, user_id: str) -> None:
        await psql_conn.execute(
            "INSERT INTO chat_participants (chat_id, user_id) VALUES ($1, $2)",
            chat_id,
            user_id,
        )

    @staticmethod
    async def remove_participant(psql_conn, chat_id: str, user_id: str) -> bool:
        deleted = await psql_conn.fetchval(
            """
            DELETE FROM chat_participants
            WHERE chat_id = $1 AND user_id = $2
            RETURNING user_id
            """,
            chat_id,
            user_id,
        )
        return deleted is not None

    @staticmethod
    async def count_participants(psql_conn, chat_id: str) -> int:
        return int(
            await psql_conn.fetchval(
                "SELECT count(*) FROM chat_participants WHERE chat_id = $1",
                chat_id,
            )
        )

    @staticmethod
    async def count_messages(psql_conn, chat_id: str) -> int:
        return int(
            await psql_conn.fetchval(
                "SELECT count(*) FROM chat_messages WHERE chat_id = $1",
                chat_id,
            )
        )

    @staticmethod
    async def list_messages(
        psql_conn,
        chat_id: str,
        skip: int,
        limit: int,
    ) -> list[ChatMessage]:
        records = await psql_conn.fetch(
            """
            SELECT id, chat_id, sender_id, message, created_at
            FROM chat_messages
            WHERE chat_id = $1
            ORDER BY created_at DESC, id DESC
            OFFSET $2
            LIMIT $3
            """,
            chat_id,
            skip,
            limit,
        )
        return [ChatPsqlRepository._message(record) for record in records]

    @staticmethod
    async def create_message(
        psql_conn,
        message_id: str,
        chat_id: str,
        sender_id: str,
        message: str,
        created_at: datetime,
    ) -> ChatMessage:
        record = await psql_conn.fetchrow(
            """
            INSERT INTO chat_messages (id, chat_id, sender_id, message, created_at)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, chat_id, sender_id, message, created_at
            """,
            message_id,
            chat_id,
            sender_id,
            message,
            created_at,
        )
        return ChatPsqlRepository._message(record)

    @staticmethod
    async def other_participant_messaged_on_date(
        psql_conn,
        chat_id: str,
        sender_id: str,
        activity_date: date,
    ) -> bool:
        return bool(
            await psql_conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM chat_messages
                    WHERE chat_id = $1
                      AND sender_id IS NOT NULL
                      AND sender_id <> $2
                      AND (created_at AT TIME ZONE 'UTC')::date = $3
                )
                """,
                chat_id,
                sender_id,
                activity_date,
            )
        )

    @staticmethod
    async def mark_closeness_activity(
        psql_conn,
        chat_id: str,
        activity_date: date,
    ) -> None:
        await psql_conn.execute(
            """
            UPDATE chats
            SET last_closeness_activity_date = $2
            WHERE id = $1
            """,
            chat_id,
            activity_date,
        )

    @staticmethod
    def _chat(record) -> Chat | None:
        if not record:
            return None
        return Chat(
            id=record["id"],
            type=ChatType(record["type"]),
            participantIds=list(record["participant_ids"]),
        )

    @staticmethod
    def _message(record) -> ChatMessage | None:
        if not record:
            return None
        return ChatMessage(
            id=record["id"],
            chatId=record["chat_id"],
            senderId=record["sender_id"],
            message=record["message"],
            createdAt=record["created_at"],
        )
